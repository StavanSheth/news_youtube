"""Modular Ingestion layer exporting canonical content models, provider adapters, and backward-compatible entrypoints."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import feedparser

from ..models import SourceItem
from ..statuses import SourceStatus
from .base import BaseProviderAdapter, CanonicalContent, SafeHttpClient
from .news_api.client import NewsApiClient
from .news_api.normalizer import NewsApiNormalizer
from .rss.client import RssClient
from .rss.normalizer import RssNormalizer, article_text, clean_html
from .rss.parser import RssParser
from .youtube.client import YouTubeClient
from .youtube.normalizer import YouTubeNormalizer
from .youtube.quota import YouTubeQuotaTracker, default_quota_tracker
from .youtube.transcripts import TranscriptStatus, YouTubeTranscriptHandler


def transcript(
    video_id: str, languages: list[str] | None = None, requested: bool = True
) -> tuple[str, dict[str, str]]:
    """Backward-compatible wrapper around YouTubeTranscriptHandler."""
    return YouTubeTranscriptHandler.fetch_transcript(video_id, languages=languages, requested=requested)


def enriched_rss(
    sources: list[dict], fetch_articles: bool = True, source_health: dict[str, dict] | None = None
) -> list[SourceItem]:
    """Ingest, validate, and normalize configured RSS sources."""
    items: list[SourceItem] = []
    for source in sources:
        if not source.get("enabled", True) or source.get("type", "rss") != "rss":
            continue
        health = source_health if source_health is not None else {}
        source_id = str(source.get("id", source.get("name", "rss")).lower().replace(" ", "-"))
        try:
            feed_url = source.get("feed_url") or source.get("url", "")
            if not feed_url:
                raise ValueError("MISSING_FEED_URL")
            parsed = feedparser.parse(feed_url)
            if getattr(parsed, "bozo", False) and not parsed.entries:
                raise ValueError(type(getattr(parsed, "bozo_exception", None)).__name__)
            health[source_id] = {
                "source_id": source_id,
                "status": (SourceStatus.HEALTHY if parsed.entries else SourceStatus.EMPTY).value,
                "entries": len(parsed.entries),
                "source": source.get("name", source_id),
                "trust_tier": source.get("trust_tier", 4),
            }
        except Exception as error:
            health[source_id] = {
                "source_id": source_id,
                "status": SourceStatus.FAILED.value,
                "entries": 0,
                "source": source.get("name", source_id),
                "trust_tier": source.get("trust_tier", 4),
                "error": type(error).__name__,
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
                    source=source.get("name", source_id),
                    priority=float(source.get("priority", 1)),
                    metadata={
                        **metadata,
                        "source_id": source_id,
                        "source_type": source.get("type", "rss"),
                        "trust_tier": source.get("trust_tier", 4),
                        "region": source.get("region", "global"),
                        "country": source.get("country", "GLOBAL"),
                        "retrieved_at": datetime.now(UTC).isoformat(),
                        "updated_at": entry.get("updated", ""),
                        "summary": summary,
                        "author": entry.get("author", ""),
                        "tags": [tag.get("term", "") for tag in entry.get("tags", [])],
                    },
                )
            )
    return items


__all__ = [
    "BaseProviderAdapter",
    "CanonicalContent",
    "NewsApiClient",
    "NewsApiNormalizer",
    "RssClient",
    "RssNormalizer",
    "RssParser",
    "SafeHttpClient",
    "TranscriptStatus",
    "YouTubeClient",
    "YouTubeNormalizer",
    "YouTubeQuotaTracker",
    "YouTubeTranscriptHandler",
    "article_text",
    "clean_html",
    "default_quota_tracker",
    "enriched_rss",
    "transcript",
]
