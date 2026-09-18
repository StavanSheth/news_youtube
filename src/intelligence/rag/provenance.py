"""Provenance verification and chain extraction for RAG context chunks."""

from __future__ import annotations

from typing import Any


def extract_provenance_chain(chunk: dict[str, Any]) -> dict[str, Any]:
    """Extract complete chain: evidence_id -> content_id -> source_id -> url."""
    meta = chunk.get("metadata", {})
    chunk_id = str(chunk.get("id", ""))
    content_id = str(meta.get("content_id", ""))
    source_id = str(meta.get("source_id", meta.get("source", "")))
    url = str(meta.get("url", meta.get("provenance", {}).get("source_url", "")))
    return {
        "evidence_id": chunk_id,
        "content_id": content_id,
        "source_id": source_id,
        "url": url,
        "published_at": meta.get("published_at"),
        "trust_tier": meta.get("trust_tier", 4),
    }


def validate_evidence_provenance(chunk: dict[str, Any]) -> tuple[bool, str]:
    """Verify that an evidence chunk has an unbroken provenance chain."""
    chain = extract_provenance_chain(chunk)
    if not chain["evidence_id"]:
        return False, "MISSING_EVIDENCE_ID"
    if not chain["content_id"]:
        return False, "MISSING_CONTENT_ID"
    if not chain["source_id"]:
        return False, "MISSING_SOURCE_ID"
    if not chain["url"] or not chain["url"].startswith(("http://", "https://")):
        return False, "INVALID_OR_MISSING_SOURCE_URL"
    return True, "VALID"
