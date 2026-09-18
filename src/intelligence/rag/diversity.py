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
    target_count: int = 4,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select high-scoring chunks while preserving source, host, event, and evidence diversity."""
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    source_counts: dict[str, int] = {}
    host_counts: dict[str, int] = {}
    event_counts: dict[str, int] = {}

    candidates = [dict(c) for c in ranked_chunks]

    # First pass: enforce diversity caps
    for chunk in candidates:
        metadata = chunk.get("metadata", {})
        source_id = str(metadata.get("source_id") or metadata.get("source", "unknown"))
        url = str(metadata.get("url", ""))
        host = _extract_host(url) or source_id
        event_id = str(metadata.get("event_id", ""))

        source_count = source_counts.get(source_id, 0)
        host_count = host_counts.get(host, 0)
        event_count = event_counts.get(event_id, 0) if event_id else 0

        can_select = (
            source_count < max_per_source
            and host_count < max_per_host
            and (not event_id or event_count < max_per_event)
        )

        if can_select:
            selected.append(chunk)
            source_counts[source_id] = source_count + 1
            host_counts[host] = host_count + 1
            if event_id:
                event_counts[event_id] = event_count + 1
        else:
            skipped.append({
                "id": chunk.get("id"),
                "source_id": source_id,
                "host": host,
                "event_id": event_id,
                "reason": "DIVERSITY_LIMIT_EXCEEDED",
            })

        if len(selected) >= target_count:
            break

    # Second pass: if we haven't reached target_count and candidates remain, fill from skipped
    if len(selected) < target_count and skipped:
        for skip_entry in list(skipped):
            chunk_id = skip_entry.get("id")
            chunk = next((c for c in candidates if c.get("id") == chunk_id and c not in selected), None)
            if chunk:
                selected.append(chunk)
                skipped.remove(skip_entry)
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
