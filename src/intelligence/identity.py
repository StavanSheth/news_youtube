"""Canonical identity rules for Set E foundation contracts.

Each public helper has domain-specific inputs. Do not replace these helpers with
one generic hash call: source, content, event, and publication identity have
different equivalence rules.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def normalize_timestamp(value: str) -> str:
    raw = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.astimezone(UTC).isoformat() if parsed.tzinfo else parsed.isoformat()
    except ValueError:
        return raw


def normalize_url(value: str) -> str:
    parsed = urlsplit(str(value or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return str(value or "").strip()
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parsed.scheme.casefold(), parsed.netloc.casefold(), path, query, ""))


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", normalize_text(value)).strip("-")
    return slug or "unknown"


def _digest(prefix: str, payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"{prefix}-{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:24]}"


def make_source_id(source_key: str) -> str:
    return f"source-{_slug(source_key)}"


def make_content_id(source_id: str, url: str = "", title: str = "", published_at: str = "", text: str = "") -> str:
    # A canonical URL identifies a source item across title edits. URL-less items
    # use normalized source/title/time/content identity instead.
    identity = {"source_id": make_source_id(source_id)}
    if normalize_url(url):
        identity["url"] = normalize_url(url)
    else:
        identity.update({"title": normalize_text(title), "published_at": normalize_timestamp(published_at), "text": normalize_text(text)})
    return _digest("content", identity)


def make_event_id(event_key: str, event_date: date | str | None = None) -> str:
    return _digest("event", {"key": normalize_text(event_key), "date": str(event_date or "")})


def make_entity_id(entity_type: str, name: str) -> str:
    return _digest("entity", {"type": _slug(entity_type), "name": normalize_text(name)})


def make_micro_topic_id(domain: str, topic: str, micro_topic: str) -> str:
    return f"micro-topic-{_slug(domain)}-{_slug(topic)}-{_slug(micro_topic)}"


def make_theme_id(theme_key: str) -> str:
    return f"theme-{_slug(theme_key)}"


def make_evidence_id(content_id: str, evidence_type: str, excerpt: str, source_url: str = "") -> str:
    return _digest(
        "evidence",
        {
            "content_id": content_id,
            "evidence_type": _slug(evidence_type),
            "excerpt": normalize_text(excerpt),
            "source_url": normalize_url(source_url),
        },
    )


def make_edition_key(edition_date: date | str, edition: str, timezone: str) -> str:
    return f"{edition_date}|{str(edition).upper()}|{timezone}"


def make_run_id(edition_key: str, started_at: datetime) -> str:
    return _digest("run", {"edition_key": edition_key, "started_at": started_at.isoformat()})


def make_publication_id(edition_key: str, newsletter_version: str = "1") -> str:
    return _digest("publication", {"edition_key": edition_key, "newsletter_version": newsletter_version})


def make_delivery_id(publication_id: str, destination: str) -> str:
    return _digest("delivery", {"publication_id": publication_id, "destination": normalize_text(destination)})
