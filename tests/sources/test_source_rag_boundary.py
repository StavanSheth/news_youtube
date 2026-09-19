"""Tests for Source -> RAG Boundary, quarantine rejection, and metadata provenance preservation."""

from __future__ import annotations

from intelligence.rag.eligibility import check_chunk_eligibility, filter_eligible_candidates
from intelligence.rag.packet import ContextPacket


def test_quarantined_source_rejected_from_rag():
    """Verify Section 12 invariant: a quarantined source is 100% rejected by RAG."""
    quarantined_chunk = {
        "id": "chunk-bad-1",
        "text": "Unverified rumors regarding AI models.",
        "metadata": {
            "source_id": "quarantined_news_feed",
            "content_id": "article-999",
            "micro_topic_id": "foundation-models",
            "url": "https://example.com/rumor",
            "published_at": "2026-09-18T12:00:00Z",
            "retrieved_at": "2026-09-18T13:00:00Z",
            "quarantined": True,
        },
    }

    eligible, reason = check_chunk_eligibility(quarantined_chunk)
    assert not eligible
    assert reason == "QUARANTINED_SOURCE"

    # Also test via explicit quarantined_sources set in filter_eligible_candidates
    regular_chunk = {
        "id": "chunk-normal-1",
        "text": "Valid research paper on transformers.",
        "metadata": {
            "source_id": "arxiv_source",
            "content_id": "paper-123",
            "micro_topic_id": "foundation-models",
            "url": "https://arxiv.org/abs/123",
            "published_at": "2026-09-18T10:00:00Z",
            "retrieved_at": "2026-09-18T11:00:00Z",
        },
    }

    candidates = [quarantined_chunk, regular_chunk]
    eligible, diag = filter_eligible_candidates(
        candidates,
        quarantined_sources={"arxiv_source"},  # arxiv is marked quarantined in registry
    )
    # Both should be rejected (one has quarantined=True, other is in quarantined_sources)
    assert len(eligible) == 0
    assert diag["rejected_count"] == 2
    assert diag["rejection_reasons"]["QUARANTINED_SOURCE"] == 2


def test_metadata_provenance_pipeline_connectivity():
    """Verify source_id, content_id, evidence_id, micro_topic_id, published_at, canonical_url

    remain connected throughout RAG into ContextPacket.
    """
    evidence = [
        {
            "id": "ev-provenance-1",
            "evidence_id": "ev-provenance-1",
            "text": "New frontier model achieves state-of-the-art results on standard benchmarks.",
            "source_id": "deepmind_blog",
            "content_id": "content-frontier-001",
            "micro_topic_id": "foundation-models",
            "published_at": "2026-09-18T08:00:00Z",
            "canonical_url": "https://deepmind.google/discover/blog/frontier-model-sota/",
            "url": "https://deepmind.google/discover/blog/frontier-model-sota/",
        }
    ]

    packet = ContextPacket.create(
        micro_topic_id="foundation-models",
        query="frontier model capabilities",
        evidence=evidence,
    )

    packet_data = packet.to_dict()
    retrieved = packet_data["retrieved_evidence"]
    assert len(retrieved) == 1
    item = retrieved[0]

    # Verify all 6 mandatory metadata provenance fields remain intact
    assert item["source_id"] == "deepmind_blog"
    assert item["content_id"] == "content-frontier-001"
    assert item["evidence_id"] == "ev-provenance-1"
    assert item["micro_topic_id"] == "foundation-models"
    assert item["published_at"] == "2026-09-18T08:00:00Z"
    assert item["canonical_url"] == "https://deepmind.google/discover/blog/frontier-model-sota/"
