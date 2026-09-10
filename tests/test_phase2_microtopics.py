from __future__ import annotations

from pathlib import Path

import pytest

from intelligence.config import load_config
from intelligence.microtopics import catalog, classify_micro_topics, coverage
from intelligence.themes import analysis_profile, select_theme
from intelligence.validation import validate_microtopics, validate_themes


ROOT = Path(__file__).parents[1]


def _entries():
    config = load_config(ROOT)
    return config, catalog(config.taxonomy, config.topics, config.microtopics)


def test_every_taxonomy_leaf_has_stable_profile_and_identity():
    config, entries = _entries()
    expected = sum(len(domain["topics"]) for domain in config.taxonomy["domains"].values())
    assert len(entries) == expected
    assert len({entry["micro_topic_id"] for entry in entries}) == expected
    assert all(entry["profile"]["analysis_contract"] for entry in entries)


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
