from __future__ import annotations

from intelligence.classification import select_micro_topic_decisions


def test_select_micro_topic_decisions_clear_primary():
    candidates = [
        {"micro_topic_id": "a", "classification_score": 0.85, "primary_threshold": 0.5, "secondary_threshold": 0.5},
        {"micro_topic_id": "b", "classification_score": 0.30, "primary_threshold": 0.5, "secondary_threshold": 0.5},
    ]
    selected = select_micro_topic_decisions(candidates)
    assert len(selected) == 1
    assert selected[0]["decision"] == "PRIMARY"
    assert selected[0]["margin"] == 0.55


def test_select_micro_topic_decisions_secondary_and_max_secondary():
    candidates = [
        {"micro_topic_id": "a", "classification_score": 0.90, "primary_threshold": 0.5, "secondary_threshold": 0.4, "max_secondary": 1},
        {"micro_topic_id": "b", "classification_score": 0.70, "primary_threshold": 0.5, "secondary_threshold": 0.4},
        {"micro_topic_id": "c", "classification_score": 0.65, "primary_threshold": 0.5, "secondary_threshold": 0.4},
    ]
    selected = select_micro_topic_decisions(candidates)
    assert len(selected) == 2
    assert selected[0]["decision"] == "PRIMARY"
    assert selected[1]["decision"] == "SECONDARY"


def test_select_micro_topic_decisions_below_primary_threshold():
    candidates = [
        {"micro_topic_id": "a", "classification_score": 0.35, "primary_threshold": 0.5, "secondary_threshold": 0.3},
    ]
    selected = select_micro_topic_decisions(candidates)
    assert selected == []


def test_select_micro_topic_decisions_hard_exclusion():
    candidates = [
        {"micro_topic_id": "a", "classification_score": 0.80, "hard_rejection_reason": "hard_exclusion:test"},
    ]
    selected = select_micro_topic_decisions(candidates)
    assert selected == []
