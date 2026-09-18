"""Phase 2B tests for hybrid BM25 + dense retrieval and RRF."""

from __future__ import annotations

from intelligence.rag.index import EvidenceIndex
from intelligence.rag.query import RetrievalRequest
from intelligence.rag.retrieval import HybridRetriever


def test_hybrid_retrieval_combines_bm25_and_dense():
    index = EvidenceIndex()
    c1 = {
        "id": "c1",
        "text": "Vector similarity search and embeddings for dense retrieval.",
        "metadata": {"content_id": "item1", "micro_topic_id": "embeddings"},
    }
    c2 = {
        "id": "c2",
        "text": "Lexical BM25 ranking based on term frequency and document frequency.",
        "metadata": {"content_id": "item2", "micro_topic_id": "rag"},
    }
    index.add(c1)
    index.add(c2)

    retriever = HybridRetriever(index, k=60)
    req = RetrievalRequest(
        query="dense retrieval and vector embeddings",
        micro_topic_id="embeddings",
        theme_id="t1",
    )
    candidates = retriever.retrieve_candidates(req, top_k=2)
    assert len(candidates) >= 1
    assert candidates[0]["id"] == "c1"
    assert "rrf_score" in candidates[0]
    assert candidates[0]["rrf_score"] > 0
