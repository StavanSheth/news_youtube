from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime

import feedparser
import requests

from .models import SourceItem
from .ingestion import transcript


def _youtube_get(path: str, params: dict, api_key: str) -> dict:
    response = requests.get(
        f"https://www.googleapis.com/youtube/v3/{path}",
        params={**params, "key": api_key},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def discover_youtube(
    channels: list[dict], topics: list[dict], api_key: str, keyword_limit: int,
    allow_global_discovery: bool = False,
) -> Iterable[SourceItem]:
    seen: set[str] = set()
    for channel in channels:
        if not channel.get("enabled") or not channel.get("id"):
            continue
        details = _youtube_get("channels", {"part": "contentDetails", "id": channel["id"]}, api_key)
        for detail in details.get("items", []):
            uploads = detail["contentDetails"]["relatedPlaylists"]["uploads"]
            listing = _youtube_get(
                "playlistItems",
                {"part": "snippet,contentDetails", "playlistId": uploads, "maxResults": 15},
                api_key,
            )
            for entry in listing.get("items", []):
                video_id = entry["contentDetails"].get("videoId")
                if video_id and video_id not in seen:
                    seen.add(video_id)
                    snippet = entry["snippet"]
                    yield _video_item(video_id, snippet, channel.get("priority", 1), channel)
    # Global YouTube search is opt-in for controlled research only. Production is channel-only.
    if not allow_global_discovery or keyword_limit <= 0:
        return
    for topic in topics:
        query = " ".join(topic.get("keywords", [])[:2])
        if not query:
            continue
        listing = _youtube_get(
            "search",
            {
                "part": "snippet",
                "q": query,
                "type": "video",
                "order": "date",
                "maxResults": keyword_limit,
            },
            api_key,
        )
        for entry in listing.get("items", []):
            video_id = entry["id"].get("videoId")
            if video_id and video_id not in seen:
                seen.add(video_id)
                yield _video_item(video_id, entry["snippet"], 1.0)


def _video_item(video_id: str, snippet: dict, priority: float, channel: dict | None = None) -> SourceItem:
    transcript_text, transcript_metadata = transcript(video_id, ["en"])
    title = snippet.get("title", "Untitled video")
    content_type = "podcast" if any(token in title.lower() for token in ("podcast", "interview", "conversation")) else "video"
    return SourceItem(
        id=video_id,
        kind="youtube",
        title=title,
        url=f"https://www.youtube.com/watch?v={video_id}",
        text=f"{snippet.get('title', '')}\n{snippet.get('description', '')}\n{transcript_text}",
        published_at=snippet.get("publishedAt", ""),
        source=snippet.get("channelTitle", "YouTube"),
        priority=float(priority),
        metadata={
            **transcript_metadata,
            "content_stream": "video",
            "content_type": content_type,
            "region": (channel or {}).get("region", "global"),
            "country": (channel or {}).get("country", "GLOBAL"),
            "source_id": (channel or {}).get("id", video_id),
        },
    )


def discover_rss(feeds: list[dict]) -> Iterable[SourceItem]:
    for feed in feeds:
        if feed.get("enabled", True) is False:
            continue
        parsed = feedparser.parse(feed["url"])
        for entry in parsed.entries:
            url = entry.get("link", "")
            if not url:
                continue
            stable_id = entry.get("id") or hashlib.sha256(url.encode()).hexdigest()
            published = entry.get("published", "")
            try:
                published = datetime(*entry.published_parsed[:6], tzinfo=UTC).isoformat()
            except (AttributeError, TypeError):
                pass
            yield SourceItem(
                id=stable_id,
                kind="news",
                title=entry.get("title", "Untitled article"),
                url=url,
                text=f"{entry.get('title', '')}\n{entry.get('summary', '')}",
                published_at=published,
                source=feed.get("name", "RSS"),
                priority=float(feed.get("priority", 1)),
            )
