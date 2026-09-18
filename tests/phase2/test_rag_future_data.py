"""Phase 2B tests for future data protection."""

from __future__ import annotations

from datetime import UTC, datetime
from intelligence.rag.eligibility import check_chunk_eligibility
from intelligence.rag.manager import ProductionRAGManager
from intelligence.rag.query import RetrievalRequest


def test_hard_eligibility_strictly_rejects_future_evidence():
    cutoff = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)
    req = RetrievalRequest(
        query="foundation model",
        micro_topic_id="foundation-models",
        theme_id="theme1",
        publication_cutoff=cutoff,
    )

    future_chunk = {
        "id": "c-future",
        "text": "Future article published ahead of cutoff.",
        "metadata": {
            "content_id": "item-future",
            "source_id": "source1",
            "url": "https://example.test/future",
            "published_at": "2026-09-18T14:00:00+00:00",
            "provenance": {"source_url": "https://example.test/future"},
        },
    }

    ok, reason = check_chunk_eligibility(future_chunk, req, publication_cutoff=cutoff)
    assert ok is False
    assert reason == "FUTURE_EVIDENCE_EXCEEDS_CUTOFF"


def test_future_data_never_enters_context_packet():
    cutoff = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)
    manager = ProductionRAGManager(settings={"retrieval_top_k": 4})

    # Add future item
    future_item = {
        "id": "item-future",
        "title": "Future News",
        "text": "Foundation model breakthrough from the future.",
        "source": "tech_wire",
        "url": "https://example.test/future",
        "kind": "news",
        "published_at": "2026-09-18T18:00:00+00:00",
        "metadata": {
            "source_id": "tech_wire",
            "content_id": "item-future",
            "published_at": "2026-09-18T18:00:00+00:00",
            "micro_topic_matches": [{"micro_topic_id": "foundation-models", "score": 0.95}],
            "provenance": {"source_url": "https://example.test/future"},
        },
    }

    classification = {
        "domain": "artificial-intelligence",
        "topic": "AI",
        "micro_topic": "foundation-models",
        "micro_topic_id": "foundation-models",
    }
    theme = {"id": "theme1", "domain": "artificial-intelligence", "questions": ["what_model"]}

    result = manager.retrieve(
        future_item,
        classification,
        theme,
        publication_cutoff_utc=cutoff,
    )
    context_packet = result["context_packet"]
    # Verify future chunk is NOT in retrieved evidence or evidence_ids
    assert len(context_packet["retrieved_evidence"]) == 0
    assert len(context_packet["evidence_ids"]) == 0
