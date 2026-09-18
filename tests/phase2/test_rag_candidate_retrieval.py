"""Phase 2B tests for candidate retrieval with BM25 and EvidenceIndex."""

from __future__ import annotations

from intelligence.rag.index import EvidenceIndex


def test_bm25_candidate_retrieval_exact_keyword():
    index = EvidenceIndex()
    c1 = {
        "id": "c1",
        "text": "Deep residual networks provide breakthrough accuracy for image classification models.",
        "metadata": {"content_id": "item1"},
    }
    c2 = {
        "id": "c2",
        "text": "Semiconductor lithography advances to extreme ultraviolet EUV systems for wafer manufacturing.",
        "metadata": {"content_id": "item2"},
    }
    index.add(c1)
    index.add(c2)

    results = index.search_lexical("residual networks", top_k=2)
    assert len(results) == 1
    chunk, score = results[0]
    assert chunk["id"] == "c1"
    assert score > 0


def test_bm25_unrelated_document_rejection():
    index = EvidenceIndex()
    c1 = {
        "id": "c1",
        "text": "Agricultural wheat production exceeds harvest expectations.",
        "metadata": {"content_id": "item1"},
    }
    index.add(c1)
    results = index.search_lexical("quantum qubit error correction", top_k=5)
    assert len(results) == 0


def test_index_remove_content_id():
    index = EvidenceIndex()
    c1 = {"id": "c1", "text": "RAG chunk 1", "metadata": {"content_id": "item1"}}
    c2 = {"id": "c2", "text": "RAG chunk 2", "metadata": {"content_id": "item1"}}
    index.add(c1)
    index.add(c2)
    assert index.total_chunks == 2

    index.remove("item1")
    assert index.total_chunks == 0
