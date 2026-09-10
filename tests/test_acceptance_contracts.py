from __future__ import annotations

from types import SimpleNamespace

from intelligence.enrichment import extract_entities
from intelligence.manager import IntelligenceManager
from intelligence.microtopics import coverage
from intelligence.provider import SOURCE_DATA_POLICY, _json_object
from intelligence.quality import evaluate_output
from intelligence.retrieval import RAGManager, retrieve
from intelligence.source_validation import validate_source_registry


def test_source_validation_reports_disabled_and_healthy_sources():
    parsed = SimpleNamespace(
        entries=[{"title": "Headline", "link": "https://source.test/story"}],
        status=200,
        bozo=False,
    )
    report = validate_source_registry(
        [
            {"id": "off", "name": "Disabled", "enabled": False, "trust_tier": 2},
            {"id": "on", "name": "Enabled", "enabled": True, "trust_tier": 1, "feed_url": "https://source.test/feed", "topics": [], "micro_topics": []},
        ],
        parser=lambda _: parsed,
    )
    assert report["off"]["status"] == "DISABLED"
    assert report["on"]["status"] == "HEALTHY"
    assert report["on"]["usable_content_count"] == 1


def test_rag_packet_filters_metadata_and_is_bounded():
    manager = RAGManager({"retrieval_chunk_size": 80, "retrieval_chunk_overlap": 10, "retrieval_top_k": 2})
    packet = manager.retrieve(
        {
            "id": "item", "kind": "news", "title": "RAG", "url": "https://source.test/rag",
            "text": "RAG retrieval reranking improves evidence selection.",
        },
        {"domain": "artificial-intelligence", "topic": "AI", "micro_topic": "rag", "signals": ["retrieval"]},
        {"id": "rag-theme", "questions": ["what_changed"]},
    )
    assert packet["status"] == "OK"
    assert packet["micro_topic"] == "rag"
    assert manager.metrics["chunks_selected"] == 1
    assert retrieve(packet["chunks"], "retrieval", filters={"kind": "youtube"}) == []


def test_provider_recovers_fenced_json_and_declares_untrusted_data_policy():
    assert _json_object("```json\n{\"facts\": [\"verified\"]}\n```")["facts"] == ["verified"]
    assert "untrusted DATA" in SOURCE_DATA_POLICY


def test_entity_registry_supports_configured_entity_types():
    registry = [
        {"name": "Example Person", "type": "person", "aliases": ["Example Person"]},
        {"name": "Example Instrument", "type": "financial-instrument", "aliases": ["Example Instrument"]},
        {"name": "Example Asset", "type": "infrastructure-asset", "aliases": ["Example Asset"]},
    ]
    found = extract_entities("Example Person discussed Example Instrument and Example Asset.", registry)
    assert {entry["type"] for entry in found} == {"person", "financial-instrument", "infrastructure-asset"}


def test_failed_ai_isolated_per_microtopic():
    class FailingProvider:
        def analyze_micro_topic(self, item, profile, evidence):
            raise TimeoutError("provider timeout")

    manager = IntelligenceManager(
        FailingProvider(),
        [{"id": "domain-fallback", "domain": "all", "micro_topic": "any", "output": {"report_type": "short_summary"}}],
        {"retrieval_chunk_size": 80, "retrieval_top_k": 1, "max_ai_attempts": 2},
    )
    result = manager.analyze(
        {"id": "x", "kind": "news", "source": "Fixture", "title": "RAG retrieval", "text": "RAG retrieval evidence"},
        [{"domain": "artificial-intelligence", "topic": "AI", "micro_topic": "rag", "signals": ["retrieval"]}],
    )
    assert result[0]["analysis_status"] == "ANALYSIS_FAILURE"
    assert manager.stats["retries"] == 1


def test_quality_rejects_uncited_facts():
    story = {
        "id": "one", "url": "https://source.test/one", "source": "Fixture",
        "importance_score": 80, "confidence_score": 75, "micro_topics": [{"micro_topic": "rag"}],
        "theme": "rag-theme", "retrieved_evidence": [{"text": "evidence"}],
        "analysis": {"facts": ["uncited"], "actionable_insights": ["verify"], "evidence": []},
    }
    result = evaluate_output([story], "# digest", "<html><body><p>ok</p></body></html>", [{"status": "UPDATE"}], {"source": {"status": "HEALTHY"}})
    assert not result["passed"]
    assert not result["checks"]["claims_cited"]


def test_quality_marks_source_failure_for_review():
    result = evaluate_output([], "# digest", "<html><body><p>ok</p></body></html>", [{"status": "SOURCE_FAILURE"}], {
        "reuters": {"source": "Reuters", "source_id": "reuters", "status": "FAILED", "error": "ValueError"},
    })
    assert result["status"] == "QUALITY_REVIEW_REQUIRED"
    assert not result["passed"]
    assert result["source_failures"][0]["error"] == "ValueError"


def test_coverage_reports_only_microtopic_scoped_source_failures():
    rows = coverage(
        [{"domain": "world", "topic": "Geopolitics", "micro_topic": "conflict"}],
        [{"domain": "world", "micro_topic": "conflict", "source_status": "SOURCE_FAILURE"}],
        {"healthy_sources": 0, "checked_sources": 1, "source_failures": [{"source_id": "reuters"}]},
    )
    assert rows[0]["status"] == "SOURCE_FAILURE"
