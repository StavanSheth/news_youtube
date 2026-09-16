from __future__ import annotations

from intelligence.evidence_scope import EvidenceScope, EvidenceScopeBuilder


def test_evidence_scope_isolation_authorization():
    scope = EvidenceScope(
        micro_topic_id="rag",
        source_content_id="content-1",
        source_id="source-1",
        evidence_ids=("e1",),
        isolation_confidence=0.85,
    )
    matching_chunk = {
        "metadata": {
            "micro_topic_id": "rag",
            "content_id": "content-1",
            "source_id": "source-1",
            "evidence_id": "e1",
            "micro_topic_matches": [{"micro_topic_id": "rag"}],
            "provenance": {"source_url": "https://example.test/article"},
        }
    }
    unmatching_chunk = {
        "metadata": {
            "micro_topic_id": "ai-agents",
            "content_id": "content-1",
            "source_id": "source-1",
            "micro_topic_matches": [{"micro_topic_id": "ai-agents"}],
            "provenance": {"source_url": "https://example.test/article"},
        }
    }
    assert scope.allows(matching_chunk) is True
    assert scope.allows(unmatching_chunk) is False


def test_scope_builder_deterministic():
    item = {
        "source": "NewsSource",
        "url": "https://example.test/ai-news",
        "title": "AI News",
        "text": "RAG and vector indexing details",
        "metadata": {"entity_ids": ["rag-entity"], "event_id": "event-123"},
    }
    classification = {"micro_topic": "rag", "routing_confidence": 0.9}
    scope = EvidenceScopeBuilder.build(item, classification)
    assert scope.micro_topic_id == "rag"
    assert scope.source_id
    assert scope.source_content_id
