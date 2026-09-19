"""Tests for ThemeContract model and validation."""

from __future__ import annotations

from intelligence.themes import ThemeContract


def test_theme_contract_valid_construction():
    contract = ThemeContract(
        theme_id="test-theme",
        micro_topic_id="test-topic",
        version="1.0.0",
        objective="Analyze test topic capability changes",
        primary_questions=("what_changed", "what_evidence_supports_it"),
        evidence_requirements=("primary_source",),
        significance_rules={"significant_if": ["milestone_reached"], "insignificant_if": ["rumor"]},
        stream_rules={"news": {"freshness": "48h"}, "video": {"focus": ["demos"]}},
        no_update_policy={"NO_MAJOR_UPDATE": "No update verified."},
    )
    ok, errors = contract.validate_completeness()
    assert ok is True
    assert not errors

    ok_strict, errors_strict = contract.validate_set_e_completeness()
    assert ok_strict is True
    assert not errors_strict


def test_theme_contract_missing_required_fields():
    incomplete = ThemeContract(theme_id="", version="")
    ok, errors = incomplete.validate_completeness()
    assert ok is False
    assert any("theme_id" in err for err in errors)
    assert any("version" in err for err in errors)


def test_theme_contract_strict_set_e_validation():
    contract = ThemeContract(
        theme_id="test-theme",
        version="1.0.0",
        primary_questions=("what_changed",),
        evidence_requirements=("primary_source",),
    )
    # Basic completeness passes
    ok, errors = contract.validate_completeness()
    assert ok is True

    # Strict Set-E requires micro_topic_id, significance_rules, stream_rules, no_update_policy
    ok_strict, errors_strict = contract.validate_set_e_completeness()
    assert ok_strict is False
    assert len(errors_strict) >= 4


def test_theme_contract_from_dict_and_to_dict():
    raw = {
        "id": "sample-theme",
        "theme_id": "sample-theme",
        "micro_topic_id": "sample-mt",
        "domain": "artificial-intelligence",
        "version": "1.0.0",
        "questions": ["q1", "q2"],
        "evidence_requirements": ["ev1"],
        "significance_rules": {"significant_if": ["sig"]},
        "stream_rules": {"news": {"freshness": "24h"}, "video": {"focus": ["demos"]}},
        "no_update_policy": {"NO_MAJOR_UPDATE": "None"},
    }
    contract = ThemeContract.from_dict(raw)
    assert contract.theme_id == "sample-theme"
    assert contract.micro_topic_id == "sample-mt"
    assert contract.domain_id == "artificial-intelligence"
    assert contract.primary_questions == ("q1", "q2")
    assert contract.evidence_requirements == ("ev1",)

    dumped = contract.to_dict()
    assert dumped["theme_id"] == "sample-theme"
    assert dumped["questions"] == ["q1", "q2"]
    assert dumped["evidence_requirements"] == ["ev1"]
