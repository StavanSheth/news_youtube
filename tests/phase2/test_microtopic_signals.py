"""Phase 2A tests for signal validation and negative signal exclusion."""

from __future__ import annotations

from pathlib import Path
from intelligence.config import load_config
from intelligence.microtopics import catalog, classify_micro_topics

ROOT = Path(__file__).parents[2]


def _setup_catalog():
    config = load_config(ROOT)
    entries = catalog(config.taxonomy, config.topics, config.microtopics, config.microtopic_matrix, config.profile_templates)
    return config, entries


def test_negative_signal_excludes_near_neighbor():
    _, entries = _setup_catalog()
    # Foundation model article explicitly mentioning no agent workflow
    item = {
        "title": "Foundation Model Inference",
        "text": "Benchmark scores for the 70B parameter model release. This is pure weight inference, not an agent workflow.",
    }
    matches = classify_micro_topics(item, entries)
    matched_slugs = {m["micro_topic"] for m in matches}
    assert "foundation-models" in matched_slugs
    assert "ai-agents" not in matched_slugs


def test_no_silent_parent_topic_leakage():
    _, entries = _setup_catalog()
    # Broad generic text about AI should NOT match specific leaves without evidence
    item = {
        "title": "Artificial Intelligence is Growing",
        "text": "The overall technology sector is investing in systems, strategy, and engineering across digital platforms.",
    }
    matches = classify_micro_topics(item, entries)
    # Generic filler must not trigger specific leaves
    assert len(matches) == 0


def test_contradiction_signal_prevents_false_qualification():
    _, entries = _setup_catalog()
    item = {
        "title": "Foundation Model Benchmark Release",
        "text": "New model weights and model benchmark results released for testing. Incidental tool use mentioned.",
    }
    matches = classify_micro_topics(item, entries)
    matched_slugs = {m["micro_topic"] for m in matches}
    assert "foundation-models" in matched_slugs
    # ai-agents has negative signal 'model benchmark', so it must be excluded
    assert "ai-agents" not in matched_slugs
