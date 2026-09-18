"""Tests for the 5-stage validation pipeline."""

from __future__ import annotations


from intelligence.validation.pipeline import validate_analysis
from intelligence.validation.provenance import validate_claim_provenance
from intelligence.validation.schema import validate_analysis_schema
from intelligence.validation.usefulness import validate_usefulness


def test_schema_validator_catches_invalid_scores():
    ok, errors = validate_analysis_schema({"importance_score": 150})
    assert ok is False
    assert any("importance_score" in e for e in errors)

    ok_valid, errors_valid = validate_analysis_schema({"importance_score": 85, "facts": ["valid fact"]})
    assert ok_valid is True
    assert errors_valid == []


def test_claim_level_provenance_requires_evidence_for_facts():
    # Fact without evidence citation should fail
    analysis_no_cite = {
        "claims": [
            {"claim_id": "c1", "text": "Model achieves 92% MMLU score", "claim_type": "FACT", "evidence_ids": []}
        ]
    }
    ok, errors = validate_claim_provenance(analysis_no_cite, context_packet={"evidence_ids": ["e1"]})
    assert ok is False
    assert any("lacks required evidence_ids" in e for e in errors)

    # Inferences marked explicitly can proceed without hard source citation
    analysis_inference = {
        "claims": [
            {"claim_id": "c2", "text": "This likely decreases API latency", "claim_type": "FACT", "inference": True, "evidence_ids": []}
        ]
    }
    ok_inf, errors_inf = validate_claim_provenance(analysis_inference, context_packet={"evidence_ids": ["e1"]})
    assert ok_inf is True
    assert errors_inf == []


def test_usefulness_flags_generic_filler():
    generic_analysis = {
        "facts": ["The update occurred."],
        "actionable_insights": ["Companies should monitor this developments carefully."],
        "summary": "This could have an impact on industry participants.",
    }
    ok, warnings = validate_usefulness(generic_analysis)
    assert ok is False
    assert any("ungrounded generic phrase" in w for w in warnings)

    concrete_analysis = {
        "facts": ["Chip pricing dropped 15% because of increased wafer yields."],
        "actionable_insights": ["Procurement teams should renegotiate Q4 contracts specifically due to supply gains."],
        "summary": "Lower packaging costs decrease total system expense by 8%.",
    }
    ok_concrete, warnings_concrete = validate_usefulness(concrete_analysis)
    assert ok_concrete is True
    assert warnings_concrete == []


def test_validation_pipeline_aggregates_all_stages():
    job = {
        "theme": {"id": "test-theme", "questions": ["what_changed"], "analysis_contract": {"forbidden_dimensions": ["cryptocurrency"]}},
        "classification": {"micro_topic_id": "test-topic", "domain": "ai"},
    }
    packet = {"evidence_ids": ["ev-1", "ev-2"]}

    # Valid analysis
    valid_payload = {
        "importance_score": 75,
        "confidence_score": 80,
        "facts": ["Model trained with 10k chips."],
        "evidence": [{"text": "Source confirms 10k chips", "source": "https://test.test"}],
        "claims": [{"claim_id": "cl-1", "text": "10k chips used", "claim_type": "FACT", "evidence_ids": ["ev-1"]}],
        "actions": [{"action_type": "SOURCE_STATED", "text": "Upgrade cluster"}],
    }
    result = validate_analysis(valid_payload, job, packet)
    assert result.is_publishable is True
    assert result.validation_status == "VALID"
    assert result.schema_status == "PASS"
    assert result.provenance_status == "PASS"

    # Analysis with forbidden dimension
    invalid_semantic = {
        **valid_payload,
        "summary": "This development integrates cryptocurrency tokens.",
    }
    result_sem = validate_analysis(invalid_semantic, job, packet)
    assert result_sem.semantic_status == "FAIL"
    assert result_sem.validation_status == "INVALID"
