"""Phase 2A tests for deterministic micro-topic classification."""

from __future__ import annotations

from pathlib import Path
from intelligence.config import load_config
from intelligence.microtopics import catalog, classify_micro_topics

ROOT = Path(__file__).parents[2]


def _setup_catalog():
    config = load_config(ROOT)
    entries = catalog(config.taxonomy, config.topics, config.microtopics, config.microtopic_matrix, config.profile_templates)
    return config, entries


def test_exact_microtopic_match():
    _, entries = _setup_catalog()
    item = {
        "title": "New Foundation Model Release",
        "text": "The company announced open weights for its new foundation model architecture with benchmark scores.",
    }
    matches = classify_micro_topics(item, entries)
    assert matches
    primary = matches[0]
    assert primary["micro_topic"] == "foundation-models"
    assert primary["classification_status"] == "PRIMARY"
    assert primary["classification_score"] >= 0.5
    assert primary["confidence"] > 0.0
    assert "foundation-models" in primary["micro_topic_id"]


def test_ambiguous_microtopic_margin_and_runner_up():
    _, entries = _setup_catalog()
    item = {
        "title": "Autonomous Agents and Foundation Models",
        "text": "The agent framework uses foundation model weights with autonomous tool use and planning memory.",
    }
    matches = classify_micro_topics(item, entries)
    assert len(matches) >= 1
    primary = matches[0]
    assert primary["runner_up_score"] >= 0.0
    assert primary["margin"] >= 0.0
    assert primary["decision_contract"]["confidence"] is not None


def test_deterministic_repeated_classification():
    _, entries = _setup_catalog()
    item = {
        "title": "Retrieval Augmented Generation with Embeddings and Reranking",
        "text": "We evaluate RAG retrieval performance with dense embeddings and cross-encoder reranking.",
    }
    run1 = classify_micro_topics(item, entries)
    run2 = classify_micro_topics(item, entries)
    assert [m["micro_topic"] for m in run1] == [m["micro_topic"] for m in run2]
    assert [m["classification_score"] for m in run1] == [m["classification_score"] for m in run2]
    assert [m["confidence"] for m in run1] == [m["confidence"] for m in run2]


def test_unrelated_microtopic_rejection():
    _, entries = _setup_catalog()
    item = {
        "title": "Agricultural Corn Harvest Report",
        "text": "Weather patterns impacted the corn yields in the Midwest during the summer harvest season.",
    }
    matches = classify_micro_topics(item, entries)
    # None of our tech/cyber/semiconductor micro-topics should match
    assert len(matches) == 0
