"""Phase 2B tests for micro-topic scoped retrieval and rejection."""

from __future__ import annotations

from intelligence.rag.index import EvidenceIndex


def test_microtopic_scoped_index_retrieval():
    index = EvidenceIndex()
    chunk_rag = {
        "id": "c-rag",
        "text": "RAG chunking strategies with vector embeddings.",
        "metadata": {
            "content_id": "item1",
            "micro_topic_id": "rag",
            "micro_topic_matches": [{"micro_topic_id": "rag", "score": 0.9}],
        },
    }
    chunk_agent = {
        "id": "c-agent",
        "text": "Agent tool use and planning loop.",
        "metadata": {
            "content_id": "item2",
            "micro_topic_id": "ai-agents",
            "micro_topic_matches": [{"micro_topic_id": "ai-agents", "score": 0.9}],
        },
    }
    index.add(chunk_rag)
    index.add(chunk_agent)

    rag_chunks = index.search_by_micro_topic("rag", top_k=5)
    assert len(rag_chunks) == 1
    assert rag_chunks[0]["id"] == "c-rag"

    agent_chunks = index.search_by_micro_topic("ai-agents", top_k=5)
    assert len(agent_chunks) == 1
    assert agent_chunks[0]["id"] == "c-agent"


def test_wrong_microtopic_rejection():
    index = EvidenceIndex()
    chunk_cyber = {
        "id": "c-cyber",
        "text": "Critical zero-day vulnerability in firewalls.",
        "metadata": {
            "content_id": "cyber1",
            "micro_topic_id": "vulnerabilities",
            "micro_topic_matches": [{"micro_topic_id": "vulnerabilities", "score": 0.95}],
        },
    }
    index.add(chunk_cyber)

    # Semiconductor query scoped to fabs
    results = index.search_by_micro_topic("fabs", top_k=5)
    assert len(results) == 0
