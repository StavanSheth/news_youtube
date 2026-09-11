from __future__ import annotations

from pathlib import Path

import pytest

from intelligence.config import load_config
from intelligence.microtopics import catalog, classify_micro_topics, coverage
from intelligence.themes import analysis_profile, select_theme
from intelligence.validation import validate_microtopics, validate_themes
from intelligence.evidence_scope import EvidenceScope


ROOT = Path(__file__).parents[1]


def _entries():
    config = load_config(ROOT)
    return config, catalog(config.taxonomy, config.topics, config.microtopics)


def test_canonical_matrix_has_236_explicit_runtime_records():
    config = load_config(ROOT)
    entries = catalog(config.taxonomy, config.topics, config.microtopics, config.microtopic_matrix)
    assert len(config.microtopic_matrix["records"]) == 236
    assert len(entries) == 236
    assert all(entry["profile_origin"] == "matrix" for entry in entries)


def test_every_taxonomy_leaf_has_stable_profile_and_identity():
    config, entries = _entries()
    expected = sum(len(domain["topics"]) for domain in config.taxonomy["domains"].values())
    assert len(entries) == expected
    assert len({entry["micro_topic_id"] for entry in entries}) == expected
    assert all(entry["profile"]["analysis_contract"] for entry in entries)
    assert all(entry["profile_origin"] in {"explicit", "derived"} for entry in entries)


def test_unconfigured_leaf_gets_observable_derived_signal_profile():
    _, entries = _entries()
    entry = next(item for item in entries if item["micro_topic"] == "ports")
    assert entry["profile_origin"] == "derived"
    assert entry["aliases"] == ["ports"]


def test_classifier_requires_specific_evidence_and_explains_result():
    _, entries = _entries()
    matches = classify_micro_topics({"title": "Foundation model benchmark release", "text": "New model capability and inference benchmark."}, entries)
    selected = {entry["micro_topic"] for entry in matches}
    assert "foundation-models" in selected
    result = next(entry for entry in matches if entry["micro_topic"] == "foundation-models")
    assert result["classification_score"] == result["classification_confidence"]
    assert result["positive_signals"]
    assert result["classification_reason"]


def test_negative_signal_prevents_agent_false_positive_for_model_article():
    _, entries = _entries()
    matches = classify_micro_topics({"title": "Foundation model benchmark", "text": "Model weights and benchmark results; no agent workflow."}, entries)
    assert "foundation-models" in {entry["micro_topic"] for entry in matches}
    assert "ai-agents" not in {entry["micro_topic"] for entry in matches}


def test_near_neighbor_articles_isolate_models_and_agents():
    _, entries = _entries()
    model = classify_micro_topics({"title": "New foundation model benchmark", "text": "The model beats the previous benchmark with no agent workflow or tool use."}, entries)
    agent = classify_micro_topics({"title": "AI agent tool-use workflow", "text": "The agent uses memory and tools; no model release or benchmark."}, entries)
    assert "foundation-models" in {entry["micro_topic"] for entry in model}
    assert "ai-agents" not in {entry["micro_topic"] for entry in model}
    assert "ai-agents" in {entry["micro_topic"] for entry in agent}
    assert "foundation-models" not in {entry["micro_topic"] for entry in agent}


def test_multiple_microtopics_require_independent_signals_and_are_deterministic():
    _, entries = _entries()
    item = {"title": "RAG agents", "text": "Agents use tool use and retrieval reranking with embeddings."}
    first = classify_micro_topics(item, entries)
    second = classify_micro_topics(item, entries)
    assert [entry["micro_topic"] for entry in first] == [entry["micro_topic"] for entry in second]
    assert {entry["micro_topic"] for entry in first} >= {"ai-agents", "rag", "embeddings"}
    assert all(entry["classification_reason"] for entry in first)


def test_theme_fallback_is_controlled_and_stream_specific():
    config, _ = _entries()
    classification = {"domain": "artificial-intelligence", "topic": "Artificial Intelligence", "micro_topic": "ai-agents"}
    theme = select_theme(classification, config.themes, {"kind": "news"})
    video = select_theme(classification, config.themes, {"kind": "youtube"})
    assert theme["resolution_level"] == "controlled_fallback"
    assert theme["fallback_used"] is True
    assert video["id"] == theme["id"] == "domain-fallback"
    assert "main_argument" in analysis_profile(classification, video, {"kind": "youtube"})["questions"]


def test_domain_family_is_distinct_from_controlled_fallback():
    config, _ = _entries()
    family = select_theme({"domain": "cybersecurity", "topic": "Cybersecurity", "micro_topic": "ransomware"}, config.themes, {"kind": "news"})
    fallback = select_theme({"domain": "quantum-computing", "topic": "Quantum", "micro_topic": "error-correction"}, config.themes, {"kind": "news"})
    assert family["resolution_level"] == "domain_family"
    assert family["fallback_used"] is True
    assert fallback["resolution_level"] == "controlled_fallback"


def test_invalid_microtopic_and_theme_configuration_fails_early():
    config, _ = _entries()
    with pytest.raises(ValueError, match="Invalid micro-topic override"):
        validate_microtopics({"defaults": config.microtopics["defaults"], "domains": {"artificial-intelligence": {"overrides": {"missing": {}}}}}, config.taxonomy)
    with pytest.raises(ValueError, match="Invalid theme micro-topic"):
        validate_themes([{"id": "bad", "domain": "finance", "micro_topic": "missing", "questions": ["what_changed"]}], config.taxonomy)


def test_coverage_never_claims_no_major_update_for_unchecked_microtopic():
    entry = {"domain": "finance", "topic": "Finance", "micro_topic": "interest-rates"}
    assert coverage([entry], [], {"healthy_sources": 1})[0]["status"] == "INSUFFICIENT_EVIDENCE"
    assert coverage([entry], [], {"healthy_sources": 1, "evaluated_micro_topics": ["finance:interest-rates"]})[0]["status"] == "NO_RELEVANT_CONTENT"


def test_coverage_uses_canonical_update_statuses_and_real_counts():
    entry = {"domain": "finance", "topic": "Finance", "micro_topic": "interest-rates"}
    row = coverage([entry], [{"domain": "finance", "micro_topic": "interest-rates", "importance_score": 50, "candidate_count": 3, "relevant_count": 2, "event_count": 1, "publishable_count": 1}], {"healthy_sources": 1, "evaluated": True})[0]
    assert row["status"] == "NO_MAJOR_UPDATE"
    assert row["candidate_count"] == 3
    assert row["relevant_count"] == 2
    assert row["event_count"] == 1


def test_manager_keeps_queries_and_contexts_isolated_per_microtopic():
    class Retriever:
        def __init__(self):
            self.metrics = {}
            self.calls = []

        def retrieve(self, item, classification, theme, event_context=None, scope=None):
            self.calls.append(classification["micro_topic"])
            return {"micro_topic": classification["micro_topic"], "query": classification["micro_topic"], "chunks": [{"text": classification["micro_topic"], "metadata": {}}], "status": "OK"}

    class Provider:
        def __init__(self):
            self.contexts = []

        def analyze_micro_topic(self, item, profile, evidence):
            self.contexts.append((profile["micro_topic"], [chunk["text"] for chunk in evidence]))
            return {"facts": [profile["micro_topic"]], "evidence": [{"type": "fact", "text": profile["micro_topic"]}]}

    retriever, provider = Retriever(), Provider()
    manager = __import__("intelligence.manager", fromlist=["MicroTopicManager"]).MicroTopicManager(provider, [{"id": "domain-fallback", "domain": "all", "micro_topic": "any", "questions": ["what_changed"]}], {"max_retrieved_context_chars": 100}, retriever)
    results = manager.analyze({"id": "x", "kind": "news", "source": "Fixture", "title": "isolated", "text": "source"}, [{"domain": "a", "topic": "A", "micro_topic": "m1"}, {"domain": "b", "topic": "B", "micro_topic": "m2"}])
    assert retriever.calls == ["m1", "m2"]
    assert provider.contexts == [("m1", ["m1"]), ("m2", ["m2"])]
    assert [result["retrieval"]["query"] for result in results] == ["m1", "m2"]


def test_manager_preserves_source_context_while_scoping_evidence():
    class Retriever:
        metrics = {}
        def retrieve(self, item, classification, theme, event_context=None, scope=None):
            return {"micro_topic": classification["micro_topic"], "query": "q", "chunks": [{"text": item["text"], "metadata": item["metadata"]}], "status": "OK"}

    class Provider:
        def __init__(self):
            self.items = []
        def analyze_micro_topic(self, item, profile, evidence):
            self.items.append(item)
            return {"facts": ["ok"], "evidence": [{"type": "fact", "text": "ok"}]}

    provider = Provider()
    manager = __import__("intelligence.manager", fromlist=["MicroTopicManager"]).MicroTopicManager(
        provider, [{"id": "domain-fallback", "domain": "all", "micro_topic": "any", "questions": ["what_changed"]}], {"max_retrieved_context_chars": 500}, Retriever()
    )
    manager.analyze({"id": "x", "kind": "news", "source": "Fixture", "title": "RAG", "text": "RAG evidence. Unrelated agent evidence."}, [{"domain": "a", "topic": "A", "micro_topic": "rag", "signals": ["RAG"]}])
    assert provider.items[0]["metadata"]["evidence_isolated"] is True
    assert provider.items[0]["relevant_context"]
    assert "Unrelated agent" not in provider.items[0]["text"]


def test_evidence_scope_is_structured_and_serializable():
    scope = EvidenceScope("micro-a", "content-a", "source-a", ("claim",), ("claim",), evidence_ids=("e1",), isolation_confidence=0.8)
    metadata = scope.to_metadata()
    assert metadata["micro_topic_id"] == "micro-a"
    assert metadata["evidence_ids"] == ["e1"]
    assert metadata["evidence_isolated"] is True
    assert scope.allows({"metadata": {"micro_topic_id": "micro-a", "content_id": "content-a", "source_id": "source-a", "evidence_id": "e1"}})
    assert not scope.allows({"metadata": {"micro_topic_id": "micro-b", "content_id": "content-a", "source_id": "source-a"}})


def test_evidence_scope_rejects_wrong_event_and_entity():
    scope = EvidenceScope("micro-a", "content-a", "source-a", allowed_events=("event-a",), allowed_entities=("entity-a",))
    base = {"micro_topic_id": "micro-a", "content_id": "content-a", "source_id": "source-a", "event_id": "event-a", "entity_ids": ["entity-a"]}
    assert scope.allows({"metadata": base})
    assert not scope.allows({"metadata": {**base, "event_id": "event-b"}})
    assert not scope.allows({"metadata": {**base, "entity_ids": ["entity-b"]}})
