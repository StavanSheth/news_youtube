from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from html import unescape
from urllib.parse import urlparse

import feedparser
import requests
from youtube_transcript_api import YouTubeTranscriptApi

from .models import SourceItem


def clean_html(value: str) -> str:
    value = re.sub(
        r"<script[^>]*>.*?</script>|<style[^>]*>.*?</style>",
        " ",
        value,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def article_text(url: str, timeout: int = 15) -> tuple[str, dict[str, str]]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "", {
            "article_status": "INVALID_URL",
            "article_reason": "Only http(s) URLs are allowed",
        }
    try:
        response = requests.get(
            url, timeout=timeout, headers={"User-Agent": "news-youtube-intelligence/1.0"}
        )
        response.raise_for_status()
        text = clean_html(response.text)
        if len(text) < 200:
            return "", {
                "article_status": "EMPTY",
                "article_reason": "Extracted page text was too short",
            }
        return text[:50000], {
            "article_status": "AVAILABLE",
            "article_retrieved_at": datetime.now(UTC).isoformat(),
        }
    except requests.RequestException as error:
        return "", {"article_status": "FAILED", "article_reason": type(error).__name__}


def transcript(
    video_id: str, languages: list[str], requested: bool = True
) -> tuple[str, dict[str, str]]:
    if not requested:
        return "", {"transcript_status": "NOT_REQUESTED"}
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=languages or None)
        rows = fetched.to_raw_data()
        text = " ".join(str(row.get("text", "")) for row in rows).strip()
        if not text:
            return "", {
                "transcript_status": "EMPTY",
                "transcript_language": getattr(fetched, "language_code", ""),
            }
        return text, {
            "transcript_status": "AVAILABLE",
            "transcript_language": getattr(fetched, "language_code", ""),
            "transcript_retrieved_at": datetime.now(UTC).isoformat(),
        }
    except Exception as error:  # Library exception types vary between transcript-api releases.
        name = type(error).__name__.lower()
        status = (
            "UNAVAILABLE"
            if any(
                token in name for token in ("disabled", "notranscript", "notranscripts", "language")
            )
            else "FAILED"
        )
        return "", {"transcript_status": status, "transcript_reason": type(error).__name__}


def enriched_rss(
    sources: list[dict], fetch_articles: bool = True, source_health: dict[str, dict] | None = None
) -> list[SourceItem]:
    items: list[SourceItem] = []
    for source in sources:
        if not source.get("enabled", True) or source.get("type", "rss") != "rss":
            continue
        health = source_health if source_health is not None else {}
        source_id = source.get("id", source.get("name", "rss").lower().replace(" ", "-"))
        try:
            feed_url = source.get("feed_url") or source.get("url", "")
            if not feed_url:
                raise ValueError("MISSING_FEED_URL")
            parsed = feedparser.parse(feed_url)
            if getattr(parsed, "bozo", False) and not parsed.entries:
                raise ValueError(type(getattr(parsed, "bozo_exception", None)).__name__)
            health[source_id] = {
                "status": "HEALTHY" if parsed.entries else "EMPTY",
                "entries": len(parsed.entries),
                "source": source.get("name", source_id),
                "trust_tier": source.get("trust_tier", 4),
            }
        except Exception as error:
            health[source_id] = {
                "status": "FAILED", "entries": 0, "source": source.get("name", source_id),
                "trust_tier": source.get("trust_tier", 4), "error": type(error).__name__,
            }
            continue
        for entry in parsed.entries:
            url = entry.get("link", "")
            if not url:
                continue
            summary = clean_html(entry.get("summary", ""))
            full_text, metadata = (
                article_text(url)
                if fetch_articles and source.get("extract_articles", True)
                else ("", {"article_status": "NOT_REQUESTED"})
            )
            published = ""
            if getattr(entry, "published_parsed", None):
                published = datetime(*entry.published_parsed[:6], tzinfo=UTC).isoformat()
            stable_id = entry.get("id") or hashlib.sha256(url.encode()).hexdigest()
            items.append(
                SourceItem(
                    id=stable_id,
                    kind="news",
                    title=clean_html(entry.get("title", "Untitled article")),
                    url=url,
                    text=full_text or summary,
                    published_at=published,
                    source=source["name"],
                    priority=float(source.get("priority", 1)),
                    metadata={
                        **metadata,
                        "source_id": source_id,
                        "source_type": source.get("type", "rss"),
                        "trust_tier": source.get("trust_tier", 4),
                        "region": source.get("region", "global"),
                        "country": source.get("country", "GLOBAL"),
                        "summary": summary,
                        "author": entry.get("author", ""),
                        "tags": [tag.get("term", "") for tag in entry.get("tags", [])],
                    },
                )
            )
    return items
