"""Tests for structured theme contract diagnostics, Set-E invariants, and machine-checkable contracts."""

from __future__ import annotations

from intelligence.themes.contracts import (
    ThemeResolution,
    validate_theme_contract,
)


def test_theme_contract_structured_diagnostics_valid():
    """Verify Section 4.2: Structured diagnostics returned on valid theme."""
    data = {
        "theme_id": "theme-mt-frontier",
        "micro_topic_id": "foundation-models",
        "topic_id": "artificial-intelligence",
        "domain_id": "technology",
        "version": "1.0.0",
        "objective": "Track benchmark improvements and architecture releases",
        "questions": ["what_capability_changed", "what_benchmark_was_evaluated"],
        "evidence_requirements": [
            "primary_arxiv_paper",
            "official_eval_release",
            "technical_report_pdf",
            "peer_reviewed_benchmark_results",
            "reproducible_validation_dataset",
        ],
        "significance_rules": {
            "significant_if": ["new_sota_on_mmlu_or_reasoning"],
            "insignificant_if": ["speculation_or_repost"],
        },
        "retrieval_intent": {
            "primary_query": "foundation models benchmark eval reasoning mmlu math coding",
            "required_concepts": ["neural_networks", "transformer_scaling", "inference_latency", "quantization_precision"],
        },
        "stream_rules": {
            "news": {"freshness": "48h"},
            "video": {"allowed_formats": ["keynotes", "technical_demos"]},
        },
        "no_update_policy": {
            "NO_MAJOR_UPDATE": "No confirmed architectural release or SOTA movement."
        },
        "entity_requirements": ["Google DeepMind", "OpenAI", "Anthropic"],
        "event_requirements": ["benchmark_release", "model_weights_open"],
        "action_rules": ["notify_analysts_if_sota_exceeds_threshold"],
        "watch_indicators": [
            "eval_loss_curves",
            "safety_card_updates",
            "alignment_evaluations",
            "context_window_expansion",
            "sparse_mixture_of_experts",
        ],
        "output_requirements": ["include_model_size", "include_quantization_details"],
        "analysis_contract": {
            "required_fields": ["model_name", "parameter_count", "eval_scores"]
        },
    }

    diag = validate_theme_contract(data)
    assert diag["theme_id"] == "theme-mt-frontier"
    assert diag["micro_topic_id"] == "foundation-models"
    assert diag["valid"] is True
    assert diag["missing_fields"] == []
    assert diag["quality_score"] >= 0.95


def test_theme_contract_structured_diagnostics_incomplete():
    """Verify Section 4.2: Structured diagnostics detects missing fields and warns."""
    incomplete_data = {
        "theme_id": "theme-broken",
        "micro_topic_id": "orphan-topic",
        "version": "1.0.0",
    }

    diag = validate_theme_contract(incomplete_data)
    assert diag["theme_id"] == "theme-broken"
    assert diag["micro_topic_id"] == "orphan-topic"
    assert diag["valid"] is False
    assert "objective" in diag["missing_fields"]
    assert "questions" in diag["missing_fields"]
    assert "evidence_requirements" in diag["missing_fields"]
    assert "stream_rules.news" in diag["missing_fields"]
    assert "stream_rules.video" in diag["missing_fields"]
    assert "no_update_policy" in diag["missing_fields"]
    assert diag["quality_score"] < 0.90


def test_theme_resolution_exposes_required_provenance():
    """Verify Section 4.5: ThemeResolution exposes all required diagnostic fields."""
    res = ThemeResolution(
        requested_level="micro_topic",
        resolved_level="micro_topic",
        fallback_used=False,
        fallback_reason="",
        theme_id="exact-theme-1",
        micro_topic_id="foundation-models",
        specificity_score=0.98,
        theme_origin="EXACT_SPEC",
        quality_score=0.97,
    )
    res_dict = res.to_dict()
    assert res_dict["theme_id"] == "exact-theme-1"
    assert res_dict["micro_topic_id"] == "foundation-models"
    assert res_dict["resolved_level"] == "micro_topic"
    assert res_dict["fallback_used"] is False
    assert res_dict["fallback_reason"] == ""
    assert res_dict["theme_origin"] == "EXACT_SPEC"
    assert res_dict["theme_specificity_score"] == 0.98
    assert res_dict["theme_quality_score"] == 0.97
