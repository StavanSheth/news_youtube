from __future__ import annotations

from pathlib import Path

import pytest

from intelligence.config import load_config
from intelligence.contracts import ContextBudget
from intelligence.microtopics import catalog, classify_micro_topics
from intelligence.registry import RuntimeRegistry


ROOT = Path(__file__).parents[1]


def test_runtime_registry_exposes_canonical_lookups():
    config = load_config(ROOT)
    registry = RuntimeRegistry(config)
    entry = registry.entries[0]
    assert registry.get_micro_topic(entry["micro_topic_id"])["micro_topic_id"] == entry["micro_topic_id"]
    assert registry.get_profile(entry["micro_topic_id"])["profile_id"]
    assert registry.get_domain(entry["domain"])
    assert registry.get_topic(entry["topic_key"])
    with pytest.raises(KeyError):
        registry.get_micro_topic("missing")


def test_generic_alias_requires_specific_signal_group():
    config = load_config(ROOT)
    entries = catalog(config.taxonomy, config.topics, config.microtopics)
    assert not {item["micro_topic"] for item in classify_micro_topics({"title": "agent", "text": ""}, entries)}


def test_context_budget_has_one_canonical_character_limit():
    budget = ContextBudget(max_context_chars=500)
    assert budget.retrieval_chars == budget.analysis_chars == budget.provider_chars == 500
