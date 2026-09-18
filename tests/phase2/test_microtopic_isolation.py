"""Phase 2A tests for micro-topic evaluation context isolation."""

from __future__ import annotations

import pytest
from intelligence.microtopics import MicroTopicDecision, MicroTopicEvaluationContext


def test_microtopic_evaluation_context_is_immutable():
    decision = MicroTopicDecision(
        micro_topic_id="foundation-models",
        domain_id="artificial-intelligence",
        topic_id="ai",
        confidence=0.88,
        classification_score=0.92,
        runner_up_score=0.45,
        margin=0.47,
        matched_signals=("foundation models", "benchmark"),
        negative_matches=(),
        classification_status="PRIMARY",
        significance=0.92,
    )
    context = MicroTopicEvaluationContext(
        micro_topic_id="foundation-models",
        classification_decision=decision,
        theme={"id": "foundation-models-theme", "questions": ["what_model"]},
        retrieval_intent={"required_concepts": ["model weights"]},
        evidence_scope={"source_id": "tech-feed"},
        budget_scope={"max_ai_calls": 1},
    )

    with pytest.raises(Exception):
        context.micro_topic_id = "ai-agents"  # Immutable dataclass

    with pytest.raises(Exception):
        context.classification_decision = decision


def test_multiple_contexts_do_not_share_mutable_state():
    d1 = MicroTopicDecision(
        micro_topic_id="m1", domain_id="d", topic_id="t", confidence=0.8, classification_score=0.8,
    )
    d2 = MicroTopicDecision(
        micro_topic_id="m2", domain_id="d", topic_id="t", confidence=0.7, classification_score=0.7,
    )
    c1 = MicroTopicEvaluationContext("m1", d1, {"theme": 1}, {}, {}, {})
    c2 = MicroTopicEvaluationContext("m2", d2, {"theme": 2}, {}, {}, {})

    assert c1.micro_topic_id != c2.micro_topic_id
    assert c1.classification_decision.micro_topic_id == "m1"
    assert c2.classification_decision.micro_topic_id == "m2"
