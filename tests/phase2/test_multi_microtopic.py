"""Phase 2A tests for multi-microtopic classification without state sharing."""

from __future__ import annotations

from pathlib import Path
from intelligence.config import load_config
from intelligence.microtopics import catalog, classify_micro_topics

ROOT = Path(__file__).parents[2]


def test_multi_microtopic_assignment_with_primary_and_secondary():
    config = load_config(ROOT)
    entries = catalog(config.taxonomy, config.topics, config.microtopics, config.microtopic_matrix, config.profile_templates)

    item = {
        "title": "AI Agents using Retrieval Augmented Generation and Foundation Models",
        "text": (
            "We present autonomous agent workflows integrating RAG vector retrieval, reranking, "
            "and open foundation model weights with benchmark comparisons."
        ),
    }
    matches = classify_micro_topics(item, entries)
    assert len(matches) >= 2

    # Exactly one PRIMARY
    primary_matches = [m for m in matches if m["classification_status"] == "PRIMARY"]
    assert len(primary_matches) == 1

    # Others are SECONDARY
    secondary_matches = [m for m in matches if m["classification_status"] == "SECONDARY"]
    assert len(secondary_matches) >= 1

    # Matched microtopics must have distinct IDs
    micro_topic_ids = [m["micro_topic_id"] for m in matches]
    assert len(micro_topic_ids) == len(set(micro_topic_ids))

    # All decisions must have independent matched signals
    for match in matches:
        assert len(match["positive_evidence"]) > 0
        assert match["confidence"] > 0.0
