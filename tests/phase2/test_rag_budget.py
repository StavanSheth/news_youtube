"""Phase 2B tests for RAG context and top-k budget enforcement."""

from __future__ import annotations

from intelligence.rag.manager import ProductionRAGManager


def test_rag_manager_respects_top_k_and_context_limits():
    manager = ProductionRAGManager(settings={"retrieval_top_k": 2, "max_retrieved_context_chars": 5000})

    item = {
        "id": "item1",
        "title": "Quantum Error Correction Breakthrough",
        "text": "Surface code qubit error correction demonstration achieves physical threshold.",
        "source": "physics_today",
        "url": "https://example.test/physics",
        "kind": "news",
        "published_at": "2026-09-18T10:00:00+00:00",
        "metadata": {
            "source_id": "physics_today",
            "content_id": "item1",
            "micro_topic_matches": [{"micro_topic_id": "quantum-hardware", "score": 0.95}],
            "provenance": {"source_url": "https://example.test/physics"},
        },
    }

    classification = {
        "domain": "quantum-computing",
        "topic": "Quantum",
        "micro_topic": "quantum-hardware",
        "micro_topic_id": "quantum-hardware",
    }
    theme = {"id": "quantum-theme", "domain": "quantum-computing", "questions": ["what_qubit"]}

    result = manager.retrieve(item, classification, theme)
    # Must not exceed retrieval_top_k (2)
    assert len(result["chunks"]) <= 2
    assert len(result["context_packet"]["retrieved_evidence"]) <= 2
