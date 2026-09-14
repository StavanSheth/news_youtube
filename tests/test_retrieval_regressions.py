from __future__ import annotations

from pathlib import Path

from intelligence.retrieval import RAGManager, RetrievalIntent, retrieve
from intelligence.evidence_scope import EvidenceScopeBuilder


ROOT = Path(__file__).parents[1]


def test_ranking_reads_each_chunk_metadata_independently():
    chunks = [
        {"text": "retrieval benchmark", "metadata": {"source_type": "type-a", "evidence_type": "article", "trust_tier": 4}},
        {"text": "retrieval benchmark", "metadata": {"source_type": "type-b", "evidence_type": "official_release", "trust_tier": 4}},
    ]
    result = retrieve(chunks, "retrieval benchmark", limit=2, retrieval_intent=RetrievalIntent(preferred_source_types=("type-b",), evidence_types=("official_release",)))
    assert result[0]["metadata"]["source_type"] == "type-b"


def test_scope_diagnostics_are_request_local_across_multiple_calls():
    manager = RAGManager({"retrieval_chunk_size": 1000, "retrieval_chunk_overlap": 0, "retrieval_top_k": 2})
    classification = {"domain": "artificial-intelligence", "topic": "AI", "micro_topic": "rag", "micro_topic_id": "rag", "signals": ["retrieval"]}
    item = {"title": "Retrieval", "url": "https://example.test/r", "source": "Fixture", "kind": "news", "text": "retrieval improves context", "metadata": {"classification": classification}}
    scope = EvidenceScopeBuilder.build(item, classification)
    first = manager.retrieve(item, classification, {"id": "rag-theme", "micro_topic": "rag"}, scope=scope)
    second = manager.retrieve({**item, "text": "unrelated content"}, classification, {"id": "rag-theme", "micro_topic": "rag"}, scope=scope)
    assert first["diagnostics"]["before_scope"] == 1
    assert second["diagnostics"]["before_scope"] == 1
    assert second["diagnostics"]["rejected_scope"] == 1
