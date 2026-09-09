from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable
from urllib.parse import urlparse

import feedparser


def _valid_http_url(value: str) -> bool:
    parsed = urlparse(value or "")
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_source_registry(
    sources: list[dict[str, Any]],
    timeout: int = 15,
    parser: Callable[[str], Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Validate every configured source without enabling inaccessible sources."""
    parse = parser or feedparser.parse
    report: dict[str, dict[str, Any]] = {}
    for source in sources:
        source_id = source.get("id", source.get("name", "source"))
        record: dict[str, Any] = {
            "source": source.get("name", source_id),
            "source_id": source_id,
            "enabled": bool(source.get("enabled", True)),
            "trust_tier": source.get("trust_tier", 4),
            "region": source.get("region", "global"),
            "country": source.get("country", "GLOBAL"),
            "topics": list(source.get("topics", [])),
            "micro_topics": list(source.get("micro_topics", [])),
            "item_count": 0,
            "usable_content_count": 0,
            "relevant_content_count": 0,
            "topics_detected": list(source.get("topics", [])),
            "micro_topics_detected": list(source.get("micro_topics", [])),
            "checked_at": datetime.now(UTC).isoformat(),
        }
        if not record["enabled"]:
            record.update({"status": "DISABLED", "failure_reason": "DISABLED_BY_CONFIGURATION"})
            report[source_id] = record
            continue
        url = source.get("feed_url") or source.get("url", "")
        record["url"] = url
        if not _valid_http_url(url):
            record.update({"status": "SOURCE_UNAVAILABLE", "failure_reason": "INVALID_URL"})
            report[source_id] = record
            continue
        try:
            parsed = parse(url)
            entries = list(getattr(parsed, "entries", []) or [])
            record["http_status"] = getattr(parsed, "status", None)
            record["item_count"] = len(entries)
            record["usable_content_count"] = sum(bool(entry.get("title") and entry.get("link")) for entry in entries)
            record["relevant_content_count"] = record["usable_content_count"]
            record["fresh"] = bool(entries)
            record["status"] = "HEALTHY" if entries else "EMPTY"
            if getattr(parsed, "bozo", False) and not entries:
                record.update({"status": "SOURCE_UNAVAILABLE", "failure_reason": "INVALID_FEED"})
        except Exception as error:
            record.update({"status": "SOURCE_UNAVAILABLE", "failure_reason": type(error).__name__})
        report[source_id] = record
    return report
