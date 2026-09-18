"""Comprehensive tests for RAG pipeline: eligibility, query, ranking, diversity, and packet."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path


from intelligence.rag.diversity import apply_diversity_filtering
from intelligence.rag.eligibility import check_chunk_eligibility
from intelligence.rag.manager import ProductionRAGManager
from intelligence.rag.query import RetrievalRequest, build_retrieval_request
from intelligence.rag.ranking import rank_evidence_chunks

ROOT = Path(__file__).parents[1]


def test_hard_eligibility_rejects_future_evidence():
    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)
    cutoff = datetime(2026, 9, 18, 11, 0, 0, tzinfo=UTC)
    request = RetrievalRequest(query="AI model", micro_topic_id="foundation-models", theme_id="theme-1")

    valid_chunk = {
        "id": "c1",
        "text": "Valid past evidence for foundation models.",
        "metadata": {
            "content_id": "item-1",
            "source_id": "source-1",
            "url": "https://example.test/1",
            "published_at": "2026-09-18T10:00:00+00:00",
            "trust_tier": 1,
            "micro_topic_id": "foundation-models",
            "provenance": {"source_url": "https://example.test/1"},
        },
    }
    future_chunk = {
        "id": "c2",
        "text": "Future evidence for foundation models.",
        "metadata": {
            "content_id": "item-2",
            "source_id": "source-1",
            "url": "https://example.test/2",
            "published_at": "2026-09-18T13:00:00+00:00",
            "trust_tier": 1,
            "micro_topic_id": "foundation-models",
            "provenance": {"source_url": "https://example.test/2"},
        },
    }

    ok_valid, reason_valid = check_chunk_eligibility(valid_chunk, request, now=now, publication_cutoff=cutoff)
    assert ok_valid is True
    assert reason_valid == "ELIGIBLE"

    ok_future, reason_future = check_chunk_eligibility(future_chunk, request, now=now, publication_cutoff=cutoff)
    assert ok_future is False
    assert reason_future == "FUTURE_EVIDENCE_EXCEEDS_CUTOFF"


def test_hard_eligibility_rejects_disabled_source_and_missing_id():
    request = RetrievalRequest(query="test", micro_topic_id="test", theme_id="theme-1")
    chunk_no_id = {"text": "some text", "metadata": {}}
    ok, reason = check_chunk_eligibility(chunk_no_id, request)
    assert ok is False
    assert reason == "MISSING_CONTENT_ID"

    chunk_disabled = {
        "id": "c3",
        "text": "text for test topic",
        "metadata": {
            "content_id": "item-3",
            "source_id": "banned_feed",
            "url": "https://example.test/3",
            "trust_tier": 2,
            "micro_topic_id": "test",
            "provenance": {"source_url": "https://example.test/3"},
        },
    }
    ok_dis, reason_dis = check_chunk_eligibility(chunk_disabled, request, disabled_sources={"banned_feed"})
    assert ok_dis is False
    assert reason_dis == "DISABLED_SOURCE"


def test_query_builder_constructs_authoritative_contract():
    req = build_retrieval_request(
        micro_topic="rag",
        theme={"id": "rag-theme", "domain": "artificial-intelligence", "retrieval_intent": {"required_concepts": ["retrieval", "embeddings"]}},
        classification={"domain": "artificial-intelligence", "topic": "AI", "micro_topic": "rag", "signals": ["reranking"]},
        cutoff=datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC),
    )
    assert req.micro_topic_id == "rag"
    assert req.theme_id == "rag-theme"
    assert "retrieval" in req.required_concepts
    assert req.publication_cutoff is not None
    assert "artificial-intelligence" in req.query


def test_composite_ranking_labels_all_score_components():
    request = RetrievalRequest(
        query="foundation model benchmark weights",
        micro_topic_id="foundation-models",
        theme_id="theme-1",
        required_concepts=("benchmark",),
    )
    chunks = [
        {
            "id": "ch-1",
            "text": "New foundation model benchmark with open model weights.",
            "metadata": {
                "source_id": "official_lab",
                "trust_tier": 1,
                "micro_topic_matches": [{"micro_topic_id": "foundation-models", "score": 0.95}],
                "published_at": "2026-09-18T10:00:00+00:00",
            },
        },
        {
            "id": "ch-2",
            "text": "Generic article mentioning model weights briefly.",
            "metadata": {
                "source_id": "random_blog",
                "trust_tier": 4,
                "published_at": "2026-08-01T00:00:00+00:00",
            },
        },
    ]
    ranked = rank_evidence_chunks(chunks, request, limit=2)
    assert len(ranked) == 2
    assert ranked[0]["id"] == "ch-1"
    details = ranked[0]["ranking_details"]
    assert "lexical_score" in details
    assert "micro_topic_score" in details
    assert "source_score" in details
    assert "freshness_score" in details
    assert "final_score" in details
    assert ranked[0]["score"] > ranked[1]["score"]


def test_diversity_filtering_prevents_single_source_flooding():
    ranked_chunks = [
        {"id": "r1", "text": "Report 1", "metadata": {"source_id": "reuters", "url": "https://reuters.test/1"}},
        {"id": "r2", "text": "Report 2", "metadata": {"source_id": "reuters", "url": "https://reuters.test/2"}},
        {"id": "r3", "text": "Report 3", "metadata": {"source_id": "reuters", "url": "https://reuters.test/3"}},
        {"id": "b1", "text": "Report B", "metadata": {"source_id": "bloomberg", "url": "https://bloomberg.test/b"}},
        {"id": "a1", "text": "Report A", "metadata": {"source_id": "apnews", "url": "https://apnews.test/a"}},
    ]
    selected, diag = apply_diversity_filtering(
        ranked_chunks,
        max_per_source=2,
        target_count=3,
    )
    selected_sources = [c["metadata"]["source_id"] for c in selected]
    assert selected_sources.count("reuters") <= 2
    assert "bloomberg" in selected_sources or "apnews" in selected_sources
    assert diag["diversity_selected"] == 3


def test_production_rag_manager_builds_context_packet():
    manager = ProductionRAGManager({"retrieval_top_k": 2, "max_retrieved_context_chars": 5000})
    item = {
        "id": "item-100",
        "title": "Foundation model pretraining",
        "text": "New foundation model architecture improves benchmark performance.",
        "source": "Research Lab",
        "url": "https://lab.test/fm",
        "kind": "news",
        "published_at": "2026-09-18T05:00:00+00:00",
    }
    classification = {
        "domain": "artificial-intelligence",
        "topic": "AI",
        "micro_topic": "foundation-models",
        "micro_topic_id": "foundation-models",
        "signals": ["foundation model"],
    }
    theme = {"id": "fm-theme", "domain": "artificial-intelligence", "questions": ["what_changed"]}
    result = manager.retrieve(item, classification, theme)
    assert result["status"] == "OK"
    assert "context_packet" in result
    packet = result["context_packet"]
    assert packet["micro_topic_id"] == "foundation-models"
    assert len(packet["retrieved_evidence"]) >= 1
    assert "ranking" in packet
    assert "diversity" in packet
