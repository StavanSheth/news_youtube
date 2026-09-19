"""RSS normalizer converting feed entries into canonical content records."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from html import unescape
from typing import Any
from urllib.parse import urlparse

import requests

from ..base import CanonicalContent


def clean_html(value: str) -> str:
    """Strip scripts, styles, and HTML tags, returning plain text."""
    if not value:
        return ""
    value = re.sub(
        r"<script[^>]*>.*?</script>|<style[^>]*>.*?</style>",
        " ",
        value,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def article_text(url: str, timeout: int = 15, max_bytes: int = 5_000_000) -> tuple[str, dict[str, str]]:
    """Fetch and extract article text from web page URL."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "", {
            "article_status": "INVALID_URL",
            "article_reason": "Only http(s) URLs are allowed",
        }
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "news-youtube-intelligence/1.0"},
            stream=True,
        )
        response.raise_for_status()
        content = response.content[:max_bytes]
        text = clean_html(content.decode("utf-8", errors="replace"))
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


class RssNormalizer:
    """Normalizes parsed RSS entries into canonical content records."""

    @classmethod
    def parse_entry_datetime(cls, entry: dict[str, Any], date_field: str) -> str:
        """Extract aware ISO 8601 timestamp from parsed struct_time."""
        parsed_tuple = getattr(entry, f"{date_field}_parsed", None) or entry.get(f"{date_field}_parsed")
        if parsed_tuple and len(parsed_tuple) >= 6:
            try:
                dt = datetime(*parsed_tuple[:6], tzinfo=UTC)
                return dt.isoformat()
            except (ValueError, TypeError):
                pass
        return ""

    @classmethod
    def normalize_entry(
        cls,
        entry: dict[str, Any],
        source: Any,
        retrieved_at: datetime | None = None,
        fetch_articles: bool = False,
    ) -> CanonicalContent | None:
        """Convert a feed entry into a CanonicalContent record."""
        url = str(entry.get("link", "")).strip()
        title = clean_html(str(entry.get("title", "Untitled article")))
        if not url or not title:
            return None

        # Distinct timestamps
        retrieved_iso = (retrieved_at or datetime.now(UTC)).isoformat()
        published_iso = cls.parse_entry_datetime(entry, "published")
        updated_iso = cls.parse_entry_datetime(entry, "updated")

        author = str(entry.get("author", "")).strip()
        raw_summary = str(entry.get("summary") or entry.get("description") or "")
        summary_text = clean_html(raw_summary)

        # Full text extraction if configured and requested
        body_text = summary_text
        article_meta: dict[str, Any] = {"article_status": "NOT_REQUESTED"}
        
        can_extract = getattr(source, "extraction_capability", "article_body") == "article_body"
        if fetch_articles and can_extract:
            extracted, article_meta = article_text(url, timeout=getattr(getattr(source, "budgets", None), "timeout_seconds", 15))
            if extracted:
                body_text = extracted

        # Metadata
        if isinstance(source, dict):
            source_id = source.get("id") or source.get("source_id") or "rss"
            source_type = source.get("type", "rss")
            role_obj = source.get("role", "NEWS")
            trust_tier = int(source.get("trust_tier", 2))
            region = source.get("region", "global")
            country = source.get("country", "GLOBAL")
            domains = tuple(source.get("domains", ()))
            topics = tuple(source.get("topics", ()))
            micro_topics = tuple(source.get("micro_topics", ()))
        else:
            source_id = getattr(source, "id", getattr(source, "source_id", "rss"))
            source_type = getattr(source, "type", "rss")
            role_obj = getattr(source, "role", "NEWS")
            trust_tier = int(getattr(source, "trust_tier", 2))
            region = getattr(source, "region", "global")
            country = getattr(source, "country", "GLOBAL")
            domains = tuple(getattr(source, "domains", ()))
            topics = tuple(getattr(source, "topics", ()))
            micro_topics = tuple(getattr(source, "micro_topics", ()))
        source_role = role_obj.value if hasattr(role_obj, "value") else str(role_obj)

        tags = [str(tag.get("term", "")).strip() for tag in entry.get("tags", []) if tag.get("term")]

        meta = {
            **article_meta,
            "tags": tags,
            "entry_id": str(entry.get("id", "")),
        }

        return CanonicalContent.create(
            source_id=source_id,
            source_type=source_type,
            source_role=source_role,
            title=title,
            canonical_url=url,
            published_at=published_iso,
            updated_at=updated_iso,
            retrieved_at=retrieved_iso,
            author=author,
            body_text=body_text,
            summary_text=summary_text,
            evidence_type="article",
            trust_tier=trust_tier,
            region=region,
            country=country,
            domains=domains,
            topics=topics,
            micro_topics=micro_topics,
            metadata=meta,
        )

    @classmethod
    def normalize(
        cls,
        parsed: Any,
        source: Any,
        fetch_articles: bool = False,
    ) -> list[CanonicalContent]:
        """Normalize all entries in a parsed feed, skipping invalid items.

        Args:
            parsed: A feedparser.FeedParserDict or any object with an ``entries`` attribute.
            source: SourceContract instance or dict with source metadata.
            fetch_articles: Whether to fetch full article bodies from entry URLs.

        Returns:
            List of successfully normalized CanonicalContent records.
        """
        retrieved_at = datetime.now(UTC)
        entries = list(getattr(parsed, "entries", []) or [])
        results: list[CanonicalContent] = []
        for entry in entries:
            try:
                item = cls.normalize_entry(entry, source, retrieved_at=retrieved_at, fetch_articles=fetch_articles)
                if item is not None:
                    results.append(item)
            except Exception:
                pass
        return results
