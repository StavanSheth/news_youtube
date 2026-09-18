"""Phase 2C tests for modular semantic validators emitting ValidationFinding."""

from __future__ import annotations

from intelligence.validation.semantic import (
    ActionabilityValidator,
    ContradictionValidator,
    GenericnessValidator,
    QuestionCoverageValidator,
    SpecificityValidator,
)


def test_question_coverage_validator():
    validator = QuestionCoverageValidator()
    theme = {"questions": ["what_changed", "why_it_matters"]}
    too_short = {"summary": "Brief."}
    findings = validator.validate(too_short, theme, "brief.")
    assert len(findings) == 1
    assert findings[0].severity == "ERROR"
    assert "too brief" in findings[0].message


def test_genericness_validator_flags_buzzwords():
    validator = GenericnessValidator()
    text = "This breakthrough is a game changer revolutionizing the industry in today's fast-paced world."
    findings = validator.validate({}, text)
    assert len(findings) >= 2
    assert all(f.severity == "WARNING" for f in findings)


def test_specificity_validator_enforces_required_dimensions():
    validator = SpecificityValidator()
    theme = {
        "analysis_contract": {
            "required_dimensions": ["business_impact"],
            "forbidden_dimensions": ["cryptocurrency"],
        }
    }
    # Missing business_impact
    findings = validator.validate({"summary": "Technical explanation only."}, theme, "technical explanation only.")
    assert any("fails to address required dimension" in f.message for f in findings)

    # Contains forbidden dimension
    findings_forbidden = validator.validate(
        {"summary": "Mentions cryptocurrency assets.", "business_impact": "high"},
        theme,
        "mentions cryptocurrency assets.",
    )
    assert any("forbidden dimension" in f.message for f in findings_forbidden)


def test_contradiction_validator_flags_negative_signal():
    validator = ContradictionValidator()
    classification = {
        "profile": {
            "negative_signals": [{"phrase": "patent litigation", "type": "exclusion"}],
        }
    }
    findings = validator.validate({}, classification, "analysis discusses patent litigation between parties.")
    assert len(findings) == 1
    assert findings[0].severity == "ERROR"
    assert "excluded contradictory concept" in findings[0].message


def test_actionability_validator_flags_vague_insights():
    validator = ActionabilityValidator()
    findings = validator.validate({"actionable_insights": ["Monitor.", "Act now."]})
    assert len(findings) == 2
    assert all(f.severity == "WARNING" for f in findings)
