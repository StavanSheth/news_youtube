"""Diversity filtering to prevent source, event, or evidence-type dominance."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def _extract_host(url: str) -> str:
    if not url:
        return ""
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def apply_diversity_filtering(
    ranked_chunks: list[dict[str, Any]],
    *,
    max_per_source: int = 2,
    max_per_host: int = 2,
    max_per_event: int = 2,
    max_per_content: int = 2,
    max_per_evidence_type: int = 3,
    target_count: int = 4,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select high-scoring chunks while preserving source, host, event, content, and evidence diversity."""
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    source_counts: dict[str, int] = {}
    host_counts: dict[str, int] = {}
    event_counts: dict[str, int] = {}
    content_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}

    candidates = [dict(c) for c in ranked_chunks]

    # First pass: enforce diversity caps
    for chunk in candidates:
        metadata = chunk.get("metadata", {})
        source_id = str(metadata.get("source_id") or metadata.get("source", "unknown"))
        url = str(metadata.get("url", ""))
        host = _extract_host(url) or source_id
        event_id = str(metadata.get("event_id", ""))
        content_id = str(metadata.get("content_id") or chunk.get("id", ""))
        evidence_type = str(metadata.get("evidence_type") or chunk.get("kind", "article"))

        source_count = source_counts.get(source_id, 0)
        host_count = host_counts.get(host, 0)
        event_count = event_counts.get(event_id, 0) if event_id else 0
        content_count = content_counts.get(content_id, 0)
        type_count = type_counts.get(evidence_type, 0)

        can_select = (
            source_count < max_per_source
            and host_count < max_per_host
            and (not event_id or event_count < max_per_event)
            and content_count < max_per_content
            and type_count < max_per_evidence_type
        )

        if can_select:
            selected.append(chunk)
            source_counts[source_id] = source_count + 1
            host_counts[host] = host_count + 1
            content_counts[content_id] = content_count + 1
            type_counts[evidence_type] = type_count + 1
            if event_id:
                event_counts[event_id] = event_count + 1
        else:
            skipped.append({
                "id": chunk.get("id"),
                "source_id": source_id,
                "host": host,
                "event_id": event_id,
                "content_id": content_id,
                "reason": "DIVERSITY_LIMIT_EXCEEDED",
            })

        if len(selected) >= target_count:
            break

    diagnostics = {
        "diversity_candidates": len(ranked_chunks),
        "diversity_selected": len(selected),
        "diversity_skipped": len(skipped),
        "selected_sources": list(source_counts.keys()),
        "selected_hosts": list(host_counts.keys()),
        "skipped_details": skipped[:10],
    }

    return selected, diagnostics
