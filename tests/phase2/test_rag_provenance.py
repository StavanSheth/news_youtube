"""Phase 2B tests for RAG provenance extraction and verification."""

from __future__ import annotations

from intelligence.rag.provenance import extract_provenance_chain, validate_evidence_provenance


def test_complete_provenance_chain_validation():
    valid_chunk = {
        "id": "chunk-101",
        "text": "TSMC 2nm manufacturing schedule confirmed.",
        "metadata": {
            "content_id": "item-202",
            "source_id": "reuters",
            "url": "https://reuters.test/tsmc-2nm",
            "published_at": "2026-09-18T10:00:00+00:00",
            "trust_tier": 1,
        },
    }
    chain = extract_provenance_chain(valid_chunk)
    assert chain["evidence_id"] == "chunk-101"
    assert chain["content_id"] == "item-202"
    assert chain["source_id"] == "reuters"
    assert chain["url"] == "https://reuters.test/tsmc-2nm"

    ok, reason = validate_evidence_provenance(valid_chunk)
    assert ok is True
    assert reason == "VALID"


def test_invalid_provenance_missing_url():
    bad_chunk = {
        "id": "chunk-102",
        "text": "Evidence without source url.",
        "metadata": {
            "content_id": "item-203",
            "source_id": "source1",
            "url": "",
        },
    }
    ok, reason = validate_evidence_provenance(bad_chunk)
    assert ok is False
    assert reason == "INVALID_OR_MISSING_SOURCE_URL"
