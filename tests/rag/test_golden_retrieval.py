"""Tests for deterministic RAG retrieval benchmark, provenance, and isolation."""

from __future__ import annotations

from intelligence.rag.benchmark import run_rag_retrieval_benchmark
from intelligence.rag.packet import ContextPacket


def test_rag_retrieval_benchmark_execution():
    """Verify RAG retrieval metrics on the golden benchmark dataset."""
    result = run_rag_retrieval_benchmark()
    assert result["status"] == "PASS"
    assert result["average_precision"] >= 0.85
    assert result["average_recall"] >= 0.85
    assert result["average_mrr"] >= 0.85
    assert result["provenance_completeness_pct"] == 100.0
    assert result["microtopic_isolation_pct"] == 100.0
    assert result["quarantine_exclusion_pct"] == 100.0
    assert result["freshness_compliance_pct"] == 100.0


def test_context_packet_invariants_and_provenance():
    """Verify ContextPacket strictly contains micro-topic identity, evidence, and provenance."""
    packet = ContextPacket.create(
        micro_topic_id="foundation-models",
        query="foundation model test query",
        evidence=[
            {
                "id": "ev-1",
                "text": "Frontier foundation model release text",
                "metadata": {
                    "source_id": "tech-daily",
                    "content_id": "cnt-1",
                    "url": "https://techdaily.test/article",
                    "published_at": "2026-09-18T10:00:00Z",
                    "trust_tier": 1,
                },
            }
        ],
    )
    d = packet.to_dict()
    assert d["micro_topic_id"] == "foundation-models"
    assert len(d["retrieved_evidence"]) == 1
    assert "query" in d
    assert "run_id" in d
    ev = d["retrieved_evidence"][0]
    assert ev["metadata"]["source_id"] == "tech-daily"
    assert ev["metadata"]["content_id"] == "cnt-1"
