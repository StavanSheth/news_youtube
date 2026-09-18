"""Phase 2A tests for theme specificity and contract completeness."""

from __future__ import annotations

from intelligence.themes import (
    ThemeContract,
    is_generic_theme,
    theme_difference_score,
    theme_specificity_score,
)


def test_theme_contract_completeness_validation():
    valid = ThemeContract(
        theme_id="rag-theme",
        micro_topic_id="rag",
        version="1.0.0",
        objective="Analyze RAG retrieval architecture improvements",
        primary_questions=("retrieval_architecture", "latency_cost_tradeoffs"),
        evidence_requirements=("benchmark", "production deployment"),
    )
    ok, errors = valid.validate_completeness()
    assert ok is True
    assert not errors

    incomplete = ThemeContract(theme_id="bad", version="")
    ok, errors = incomplete.validate_completeness()
    assert ok is False
    assert len(errors) >= 2


def test_generic_template_rejection():
    generic = {
        "id": "generic-template",
        "questions": ["What changed?", "Why does it matter?", "What should we watch?"],
        "output": {"report_type": "summary"},
    }
    assert is_generic_theme(generic) is True

    specific = {
        "id": "rag-specific",
        "questions": ["What retrieval architecture changed?", "What reranking benchmark is cited?"],
        "retrieval_intent": {"required_concepts": ["retrieval", "embeddings"]},
        "watch_items": ["latency", "chunk size"],
    }
    assert is_generic_theme(specific) is False


def test_theme_difference_across_sibling_microtopics():
    theme_rag = {
        "questions": ["retrieval_architecture", "latency_cost_tradeoffs"],
        "retrieval_intent": {"required_concepts": ["embeddings", "reranking", "vector"]},
        "evidence": ["benchmark", "recall"],
        "watch_items": ["latency", "index build time"],
        "analysis_contract": {"objective": "evaluate retrieval accuracy"},
    }
    theme_agent = {
        "questions": ["agent_orchestration", "tool_accuracy"],
        "retrieval_intent": {"required_concepts": ["tool use", "planning", "memory"]},
        "evidence": ["execution trace", "tool call log"],
        "watch_items": ["autonomy level", "error rate"],
        "analysis_contract": {"objective": "evaluate tool execution autonomy"},
    }
    diff = theme_difference_score(theme_rag, [theme_agent])
    assert diff > 0.5
    assert theme_specificity_score(theme_rag) >= 0.5
