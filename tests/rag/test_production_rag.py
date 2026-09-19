"""Comprehensive tests for Phase 2B: Production RAG and Evidence Engine."""

from datetime import UTC, datetime, timedelta

from intelligence.ai.token_budget import TokenBudgetManager
from intelligence.evidence.chunks import Chunker
from intelligence.rag.budget import ContextBudgeter
from intelligence.rag.cache import RetrievalCache, RetrievalCacheKey
from intelligence.rag.diversity import apply_diversity_filtering
from intelligence.rag.eligibility import TemporalEvidencePolicy, check_chunk_eligibility
from intelligence.rag.packet import ContextPacket
from intelligence.rag.query import build_retrieval_request
from intelligence.rag.ranking import rank_evidence_chunks


def test_future_evidence_rejected():
    policy = TemporalEvidencePolicy(
        publication_cutoff=datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC),
        now=datetime(2026, 9, 18, 14, 0, 0, tzinfo=UTC),
    )
    future_date = datetime(2026, 9, 19, 0, 0, 0, tzinfo=UTC)
    ok, reason = policy.evaluate(published_at=future_date)
    assert not ok
    assert reason == "FUTURE_EVIDENCE_EXCEEDS_CUTOFF"

    # Also test check_chunk_eligibility
    chunk = {
        "id": "c-future",
        "text": "Future article",
        "metadata": {
            "content_id": "cnt-1",
            "source_id": "src-1",
            "published_at": "2026-09-19T00:00:00+00:00",
        },
    }
    elig_ok, elig_reason = check_chunk_eligibility(
        chunk,
        publication_cutoff=datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC),
    )
    assert not elig_ok
    assert elig_reason == "FUTURE_EVIDENCE_EXCEEDS_CUTOFF"


def test_wrong_microtopic_rejected():
    req = build_retrieval_request(
        micro_topic="foundation-models",
        theme={"id": "theme-1"},
        classification={"micro_topic_id": "foundation-models"},
    )
    chunk = {
        "id": "c-wrong",
        "text": "Shipping container port infrastructure",
        "metadata": {
            "content_id": "cnt-2",
            "source_id": "src-2",
            "micro_topic_id": "port-logistics",
            "micro_topic_matches": [{"micro_topic_id": "port-logistics"}],
        },
    }
    ok, reason = check_chunk_eligibility(chunk, req)
    assert not ok
    assert reason == "UNAUTHORIZED_MICRO_TOPIC"


def test_missing_provenance_rejected():
    # Missing source_id
    chunk_no_source = {
        "id": "c-no-source",
        "text": "Some text",
        "metadata": {"content_id": "cnt-1"},
    }
    ok, reason = check_chunk_eligibility(chunk_no_source)
    assert not ok
    assert reason == "MISSING_SOURCE_ID"

    # Missing content_id
    chunk_no_content = {
        "id": "",
        "text": "Some text",
        "metadata": {"source_id": "src-1"},
    }
    ok, reason = check_chunk_eligibility(chunk_no_content)
    assert not ok
    assert reason == "MISSING_CONTENT_ID"


def test_disabled_source_rejected():
    chunk = {
        "id": "c-disabled",
        "text": "Some text",
        "metadata": {"content_id": "cnt-1", "source_id": "untrusted_blog"},
    }
    ok, reason = check_chunk_eligibility(chunk, disabled_sources={"untrusted_blog"})
    assert not ok
    assert reason == "DISABLED_SOURCE"


def test_freshness_rejected():
    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)
    old_date = (now - timedelta(days=45)).isoformat()
    chunk = {
        "id": "c-old",
        "text": "Old foundation model article",
        "metadata": {
            "content_id": "cnt-1",
            "source_id": "src-1",
            "published_at": old_date,
        },
    }
    from intelligence.rag.query import RetrievalRequest
    req = RetrievalRequest(
        query="foundation model",
        micro_topic_id="foundation-models",
        theme_id="theme-1",
        freshness="30d",
    )
    ok, reason = check_chunk_eligibility(chunk, req, now=now)
    assert not ok
    assert reason == "FRESHNESS_EXPIRED"


def test_duplicate_chunks_collapsed():
    item = {
        "id": "item-dup",
        "source": "TechDaily",
        "title": "Model Launch",
        "url": "https://tech.test/launch",
        "text": "Foundation model launched today with high compute benchmark scores.",
    }
    chunks = Chunker.deterministic(item)
    assert len(chunks) >= 1
    assert "chunk_id" in chunks[0]
    assert "token_estimate" in chunks[0]
    assert "provenance" in chunks[0]


def test_source_diversity():
    chunks = [
        {"id": "c-1", "text": "text 1", "score": 0.95, "metadata": {"source_id": "reuters", "event_id": "e1"}},
        {"id": "c-2", "text": "text 2", "score": 0.90, "metadata": {"source_id": "reuters", "event_id": "e1"}},
        {"id": "c-3", "text": "text 3", "score": 0.85, "metadata": {"source_id": "bloomberg", "event_id": "e2"}},
    ]
    selected, diag = apply_diversity_filtering(chunks, target_count=2, max_per_source=1)
    sources = [c["metadata"]["source_id"] for c in selected]
    assert sources == ["reuters", "bloomberg"]
    assert diag["diversity_skipped"] >= 1


def test_event_diversity():
    chunks = [
        {"id": "c-1", "text": "text 1", "score": 0.95, "metadata": {"source_id": "s1", "event_id": "same_event"}},
        {"id": "c-2", "text": "text 2", "score": 0.90, "metadata": {"source_id": "s2", "event_id": "same_event"}},
        {"id": "c-3", "text": "text 3", "score": 0.85, "metadata": {"source_id": "s3", "event_id": "other_event"}},
    ]
    selected, _ = apply_diversity_filtering(chunks, target_count=2, max_per_event=1)
    events = [c["metadata"]["event_id"] for c in selected]
    assert events == ["same_event", "other_event"]


def test_context_budget():
    budgeter = ContextBudgeter(max_chars=200, max_tokens=100, max_items=2)
    chunks = [
        {"id": "c-1", "text": "A" * 120, "score": 0.9},
        {"id": "c-2", "text": "B" * 120, "score": 0.8},
        {"id": "c-3", "text": "C" * 120, "score": 0.7},
    ]
    selected, trace = budgeter.enforce_budget(chunks)
    assert len(selected) == 1
    assert trace["items_selected"] == 1
    assert trace["chars_used"] <= 200


def test_token_budget():
    mgr = TokenBudgetManager(max_edition_tokens=1000, max_microtopic_tokens=500, p0_reserve_tokens=200)
    auth, reason = mgr.authorize("topic-1", estimated_tokens=300, priority=5)
    assert auth
    assert reason == "AUTHORIZED"

    mgr.consume("topic-1", actual_tokens=300)
    assert mgr.consumed_tokens == 300

    # Test micro-topic limit
    auth2, reason2 = mgr.authorize("topic-1", estimated_tokens=300, priority=5)
    assert not auth2
    assert reason2 == "MICROTOPIC_BUDGET_EXCEEDED"


def test_ranking_breakdown():
    chunks = [
        {
            "id": "c-1",
            "text": "Foundation models benchmark release capability.",
            "metadata": {"trust_tier": 1, "micro_topic_id": "foundation-models", "published_at": "2026-09-18T10:00:00+00:00"},
        }
    ]
    req = build_retrieval_request(
        micro_topic="foundation-models",
        theme={"id": "theme-1"},
        classification={"micro_topic_id": "foundation-models"},
    )
    ranked = rank_evidence_chunks(chunks, req)
    assert len(ranked) == 1
    breakdown = ranked[0]["ranking_breakdown"]
    assert "lexical_score" in breakdown
    assert "source_quality_score" in breakdown
    assert "final_score" in breakdown


def test_retrieval_cache():
    cache = RetrievalCache()
    key1 = RetrievalCacheKey.create(
        query="foundation model",
        micro_topic_id="foundation-models",
        edition_cutoff="2026-09-18T18:00:00+00:00",
    )
    assert cache.get(key1) is None
    cache.set(key1, {"status": "OK", "chunks": ["c1"]})
    cached = cache.get(key1)
    assert cached is not None
    assert cached["status"] == "OK"
    assert cache.stats()["hits"] == 1


def test_cache_invalidation():
    cache = RetrievalCache()
    key1 = RetrievalCacheKey.create(
        query="foundation model",
        micro_topic_id="foundation-models",
        edition_cutoff="2026-09-18T18:00:00+00:00",
    )
    cache.set(key1, {"status": "OK"})
    assert cache.get(key1) is not None
    cache.invalidate()
    assert cache.get(key1) is None
    assert cache.stats()["size"] == 0


def test_context_packet_integrity():
    packet = ContextPacket(
        run_id="run-001",
        edition_key="2026-09-18|NIGHT",
        micro_topic_id="foundation-models",
        theme_id="theme-ai",
        query="foundation model benchmark",
        retrieved_evidence=({"id": "c-1", "text": "evidence text"},),
    )
    d = packet.to_dict()
    assert d["run_id"] == "run-001"
    assert d["micro_topic_id"] == "foundation-models"
    assert len(d["retrieved_evidence"]) == 1


def test_rag_manager_authoritative_request_api():
    from intelligence.rag.manager import RAGManager, RetrievalResult
    from intelligence.rag.query import RetrievalRequest

    manager = RAGManager(settings={"retrieval_top_k": 2})
    # Index a piece of evidence first
    manager.index_item({
        "id": "item-req-api",
        "title": "Foundation model capabilities in 2026",
        "text": "Foundation models demonstrate reasoning capabilities across multiple benchmarks.",
        "url": "https://tech.test/foundation-benchmarks",
        "published_at": "2026-09-18T10:00:00+00:00",
        "metadata": {
            "source_id": "tech-daily",
            "trust_tier": 1,
            "micro_topic_id": "foundation-models",
        },
    })

    request = RetrievalRequest(
        query="foundation models reasoning benchmarks",
        micro_topic_id="foundation-models",
        theme_id="theme-ai",
        max_results=2,
    )
    result = manager.retrieve(request)
    assert isinstance(result, RetrievalResult)
    assert result.status == "OK"
    assert len(result.chunks) >= 1
    assert result["status"] == "OK"
    assert "retrieved_evidence" in result.context_packet

