from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime

import feedparser
import requests
from youtube_transcript_api import YouTubeTranscriptApi

from .models import SourceItem


def _youtube_get(path: str, params: dict, api_key: str) -> dict:
    response = requests.get(
        f"https://www.googleapis.com/youtube/v3/{path}",
        params={**params, "key": api_key},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def discover_youtube(
    channels: list[dict], topics: list[dict], api_key: str, keyword_limit: int
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
                    yield _video_item(video_id, snippet, channel.get("priority", 1))
    # Topic searches are intentionally capped; channel uploads are the primary discovery path.
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


def _video_item(video_id: str, snippet: dict, priority: float) -> SourceItem:
    transcript = ""
    try:
        transcript = " ".join(
            part["text"] for part in YouTubeTranscriptApi().fetch(video_id).to_raw_data()
        )
    except Exception:
        pass  # Metadata still provides a useful, safely degraded source.
    return SourceItem(
        id=video_id,
        kind="youtube",
        title=snippet.get("title", "Untitled video"),
        url=f"https://www.youtube.com/watch?v={video_id}",
        text=f"{snippet.get('title', '')}\n{snippet.get('description', '')}\n{transcript}",
        published_at=snippet.get("publishedAt", ""),
        source=snippet.get("channelTitle", "YouTube"),
        priority=float(priority),
        metadata={"transcript_available": bool(transcript)},
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
