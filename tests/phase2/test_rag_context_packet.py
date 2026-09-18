"""Phase 2B tests for ContextPacket immutability and complete traces."""

from __future__ import annotations

import pytest
from intelligence.rag.packet import ContextPacket


def test_context_packet_immutability():
    evidence = (
        {
            "id": "e1",
            "text": "Evidence 1",
            "metadata": {"content_id": "c1", "source_id": "s1"},
        },
    )
    packet = ContextPacket.create(
        micro_topic_id="rag",
        query="RAG embeddings",
        evidence=evidence,
        retrieval_trace={"candidates": 10},
        ranking_trace={"ranked": 4},
        diversity_trace={"skipped": 1},
        budget_trace={"chars_used": 500},
    )

    # Verify immutability
    with pytest.raises(Exception):
        packet.micro_topic_id = "ai-agents"

    # Verify fields
    assert packet.micro_topic_id == "rag"
    assert packet.query == "RAG embeddings"
    assert "e1" in packet.evidence_ids
    assert "c1" in packet.content_ids
    assert "s1" in packet.source_ids
    assert packet.retrieval_trace["candidates"] == 10
    assert packet.ranking_trace["ranked"] == 4
    assert packet.diversity_trace["skipped"] == 1
    assert packet.budget_trace["chars_used"] == 500
