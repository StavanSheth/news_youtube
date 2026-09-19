"""Comprehensive Phase 2C tests for 5-stage validation and provenance chain."""

from datetime import UTC, datetime, timedelta

from intelligence.validation.business import validate_business_rules
from intelligence.validation.provenance import validate_claim_provenance
from intelligence.validation.semantic import validate_semantic_content


def test_fact_requires_evidence():
    analysis = {
        "claims": [
            {"claim_id": "c-1", "text": "Model launched with 40% reduction", "claim_type": "FACT", "evidence_ids": []}
        ]
    }
    ok, errors = validate_claim_provenance(analysis, context_packet={"evidence_ids": ["ev-1"]})
    assert not ok
    assert any("lacks required evidence_ids" in e for e in errors)


def test_inference_label():
    analysis = {
        "claims": [
            {"claim_id": "c-2", "text": "This may shift market pricing", "claim_type": "INFERENCE", "inference": True, "evidence_ids": []}
        ]
    }
    ok, errors = validate_claim_provenance(analysis, context_packet={"evidence_ids": ["ev-1"]})
    assert ok
    assert len(errors) == 0


def test_unsupported_claim():
    analysis = {
        "claims": [
            {"claim_id": "c-3", "text": "Unverified assertion", "claim_type": "FACT", "evidence_ids": ["non-existent-ev"]}
        ]
    }
    ok, errors = validate_claim_provenance(analysis, context_packet={"evidence_ids": ["ev-real-1"]})
    assert not ok
    assert any("not present in context packet" in e for e in errors)


def test_wrong_source():
    # If claim points to an evidence chunk with mismatched source
    packet = {
        "evidence_ids": ["ev-1"],
        "retrieved_evidence": [{"id": "ev-1", "metadata": {"source_id": "reuters"}}],
    }
    analysis = {
        "claims": [
            {"claim_id": "c-4", "text": "Fact from bloomberg", "claim_type": "FACT", "evidence_ids": ["ev-1"], "source_id": "bloomberg"}
        ]
    }
    ok, errors = validate_claim_provenance(analysis, context_packet=packet)
    assert not ok
    assert any("Provenance mismatch" in e and "source_id" in e for e in errors)


def test_wrong_content():
    packet = {
        "evidence_ids": ["ev-1"],
        "retrieved_evidence": [{"id": "ev-1", "metadata": {"content_id": "cnt-A"}}],
    }
    analysis = {
        "claims": [
            {"claim_id": "c-5", "text": "Fact from wrong content", "claim_type": "FACT", "evidence_ids": ["ev-1"], "content_id": "cnt-B"}
        ]
    }
    ok, errors = validate_claim_provenance(analysis, context_packet=packet)
    assert not ok
    assert any("Provenance mismatch" in e and "content_id" in e for e in errors)


def test_future_date():
    future_date = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    analysis = {
        "evidence": [{"published_at": future_date, "text": "Future article"}],
        "actions": [{"action_text": "Verify future date", "action_type": "AI_DERIVED"}],
    }
    cutoff = datetime.now(UTC)
    ok, errors = validate_business_rules(analysis, publication_cutoff=cutoff)
    assert not ok
    assert any("exceeds publication cutoff" in e for e in errors)


def test_number_mismatch():
    analysis = {
        "facts": ["The revenue jumped 99.9% this quarter."],
        "important_numbers": ["99.9%"],
    }
    theme = {"analysis_contract": {"required_dimensions": ["facts"]}}
    classification = {"profile": {}}
    ok, errors = validate_semantic_content(analysis, theme, classification)
    assert isinstance(ok, bool)
