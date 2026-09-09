from __future__ import annotations

from pathlib import Path

from intelligence.config import load_config
from intelligence.events import group_events
from intelligence.quality import evaluate_output
from intelligence.manager import IntelligenceManager
from intelligence.microtopics import catalog, classify_micro_topics, coverage
from intelligence.retrieval import retrieve, semantic_chunks
from intelligence.themes import analysis_profile, select_theme


ROOT = Path(__file__).parents[1]


def test_runtime_catalog_uses_taxonomy_and_assigns_multiple_microtopics():
    config = load_config(ROOT)
    entries = catalog(config.taxonomy, config.topics)
    matches = classify_micro_topics(
        {"title": "AI agents improve RAG workflows", "text": "AI agents use retrieval and embeddings."}, entries
    )
    keys = {match["micro_topic"] for match in matches if match["domain"] == "artificial-intelligence"}
    assert "ai-agents" in keys
    assert "rag" in keys
    assert all(match["signals"] for match in matches)


def test_retrieval_is_bounded_and_micro_topic_specific():
    item = {
        "id": "x", "title": "RAG evaluation", "url": "https://example.test/x",
        "source": "fixture", "kind": "news",
        "text": "RAG retrieval reranking improves context relevance.\n\nGPU supply and rates are unrelated.",
    }
    chunks = semantic_chunks(item, size=120, overlap=10)
    selected = retrieve(chunks, "rag retrieval reranking context relevance", limit=1)
    assert len(selected) == 1
    assert "retrieval" in selected[0]["text"].lower()
    assert selected[0]["metadata"]["url"] == item["url"]


def test_theme_profile_differs_for_news_and_video():
    config = load_config(ROOT)
    classification = {
        "domain": "artificial-intelligence", "topic": "Artificial Intelligence",
        "micro_topic": "ai-agents", "priority": 10, "signals": ["agents"],
    }
    news_theme = select_theme(classification, config.themes, {"kind": "news"})
    video_theme = select_theme(classification, config.themes, {"kind": "youtube"})
    assert news_theme["micro_topic"] == classification["micro_topic"]
    assert analysis_profile(classification, video_theme, {"kind": "youtube"})["content_stream"] == "video"
    assert "main_argument" in video_theme["questions"]


def test_coverage_distinguishes_no_update_from_missing_evidence():
    entries = [{"domain": "finance", "topic": "Finance", "micro_topic": "interest-rates"}]
    assert coverage(entries, [], {"healthy_sources": 1})[0]["status"] == "NO_MAJOR_UPDATE"
    assert coverage(entries, [], {"healthy_sources": 0})[0]["status"] == "INSUFFICIENT_EVIDENCE"
    assert coverage(
        entries,
        [{"domain": "finance", "micro_topic": "interest-rates", "evidence_available": False}],
        {"healthy_sources": 1},
    )[0]["status"] == "INSUFFICIENT_EVIDENCE"


def test_event_grouping_does_not_merge_items_with_missing_hashes():
    groups = group_events([
        {"id": "one", "title": "GPU launch", "url": "https://a.test/one", "source": "A"},
        {"id": "two", "title": "Interest rate decision", "url": "https://b.test/two", "source": "B"},
    ])
    assert len(groups) == 2


def test_quality_gate_requires_structured_fields_and_valid_html():
    story = {
        "id": "one", "url": "https://example.test/one", "source": "Fixture",
        "importance_score": 80, "confidence_score": 75, "micro_topics": [{"micro_topic": "rag"}],
        "theme": "artificial-intelligence-rag-analysis", "retrieved_evidence": [{"text": "evidence"}],
        "analysis": {"facts": ["confirmed"], "actionable_insights": ["test" ], "evidence": [{"type": "fact", "text": "confirmed", "source_url": "https://example.test/one"}]},
    }
    result = evaluate_output([story], "# digest", "<html><body><p>ok</p></body></html>", [{"status": "UPDATE"}], {"source": {"status": "HEALTHY"}})
    assert result["passed"]
    assert result["scores"]["overall"] == 100


class _Provider:
    def __init__(self):
        self.calls = []

    def analyze_micro_topic(self, item, profile, evidence):
        self.calls.append((profile["micro_topic"], sum(len(chunk["text"]) for chunk in evidence)))
        return {"facts": ["fixture fact"], "confidence": 0.8, "evidence": [{"type": "fact", "text": "fixture fact"}]}


def test_manager_routes_each_microtopic_with_bounded_context():
    provider = _Provider()
    manager = IntelligenceManager(
        provider,
        [{"id": "domain-fallback", "domain": "all", "micro_topic": "any", "output": {"report_type": "short_summary"}}],
        {"retrieval_chunk_size": 80, "retrieval_chunk_overlap": 10, "retrieval_top_k": 2, "max_retrieved_context_chars": 100},
    )
    classifications = [
        {"domain": "artificial-intelligence", "topic": "AI", "micro_topic": "rag", "signals": ["retrieval"]},
        {"domain": "artificial-intelligence", "topic": "AI", "micro_topic": "ai-agents", "signals": ["agents"]},
    ]
    results = manager.analyze({"id": "x", "kind": "news", "title": "RAG agents", "text": "retrieval agents " * 100}, classifications)
    assert {result["classification"]["micro_topic"] for result in results} == {"rag", "ai-agents"}
    assert len(provider.calls) == 2
    assert all(size <= 100 for _, size in provider.calls)
