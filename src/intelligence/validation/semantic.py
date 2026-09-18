"""Semantic validation ensuring alignment with micro-topic questions and contracts."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True)
class ValidationFinding:
    severity: str  # "ERROR" or "WARNING"
    validator_name: str
    message: str
    path: str = ""
    fix_suggestion: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "validator_name": self.validator_name,
            "message": self.message,
            "path": self.path,
            "fix_suggestion": self.fix_suggestion,
        }


class QuestionCoverageValidator:
    """Verifies that all required theme questions have answers in the analysis."""
    name = "QuestionCoverageValidator"

    def validate(self, analysis: dict[str, Any], theme: dict[str, Any], text_content: str) -> list[ValidationFinding]:
        findings = []
        questions = theme.get("questions", [])
        if questions and len(text_content) < 30:
            findings.append(ValidationFinding(
                severity="ERROR",
                validator_name=self.name,
                message="Analysis is too brief to address required theme questions",
                path="summary",
                fix_suggestion="Expand analysis with concrete facts answering theme questions",
            ))
        return findings


class GenericnessValidator:
    """Detects and rejects corporate filler and generic boilerplate phrases."""
    name = "GenericnessValidator"

    GENERIC_PATTERNS = [
        r"game[ -]?changer",
        r"revolutioniz(e|ing) the industry",
        r"paradigm shift",
        r"in today'?s fast[- ]paced (world|environment|landscape)",
        r"only time will tell",
        r"it remains to be seen",
        r"synergistic value",
        r"unlock(ing)? new possibilities",
    ]

    def validate(self, analysis: dict[str, Any], text_content: str) -> list[ValidationFinding]:
        findings = []
        for pat in self.GENERIC_PATTERNS:
            if re.search(pat, text_content, re.IGNORECASE):
                findings.append(ValidationFinding(
                    severity="WARNING",
                    validator_name=self.name,
                    message=f"Analysis contains generic boilerplate: '{pat}'",
                    path="summary",
                    fix_suggestion="Replace vague cliché with verifiable metrics or concrete outcomes",
                ))
        return findings


class SpecificityValidator:
    """Enforces specific required dimensions and rejects forbidden dimensions."""
    name = "SpecificityValidator"

    DIMENSION_FIELD_ALIASES: dict[str, list[str]] = {
        "summary": ["summary", "interpretation", "changes"],
        "actions": ["actions", "actionable_insights"],
        "sources": ["sources", "evidence"],
        "evidence": ["evidence", "facts"],
        "implications": ["implications", "interpretation", "risks", "opportunities"],
        "what_changed": ["changes", "facts"],
        "why_it_matters": ["interpretation", "implications"],
        "business_impact": ["implications", "risks", "opportunities"],
    }

    def validate(self, analysis: dict[str, Any], theme: dict[str, Any], text_content: str) -> list[ValidationFinding]:
        findings = []
        required_dimensions = theme.get("analysis_contract", {}).get("required_dimensions", [])
        for dim in required_dimensions:
            dim_key = str(dim).strip().lower()
            aliases = self.DIMENSION_FIELD_ALIASES.get(dim_key, [dim_key])
            has_field = any(bool(analysis.get(alias)) for alias in aliases)
            if not (has_field or dim_key in text_content or dim_key in analysis):
                findings.append(ValidationFinding(
                    severity="ERROR",
                    validator_name=self.name,
                    message=f"Analysis fails to address required dimension: '{dim}'",
                    path=dim_key,
                    fix_suggestion=f"Provide explicit section or field for '{dim}'",
                ))

        forbidden_dimensions = theme.get("analysis_contract", {}).get("forbidden_dimensions", [])
        for forbidden in forbidden_dimensions:
            if forbidden and forbidden.lower() in text_content:
                findings.append(ValidationFinding(
                    severity="ERROR",
                    validator_name=self.name,
                    message=f"Analysis contains forbidden dimension for theme: '{forbidden}'",
                    path="forbidden",
                    fix_suggestion=f"Remove discussion of '{forbidden}' from output",
                ))
        return findings


class ContradictionValidator:
    """Checks for internal contradictions or claims violating negative signals."""
    name = "ContradictionValidator"

    def validate(self, analysis: dict[str, Any], classification: dict[str, Any], text_content: str) -> list[ValidationFinding]:
        findings = []
        negative_signals = classification.get("profile", {}).get("negative_signals", [])
        for neg in negative_signals:
            phrase = (neg.get("phrase") if isinstance(neg, dict) else neg) or ""
            neg_type = (neg.get("type") if isinstance(neg, dict) else "")
            if neg_type == "exclusion" and phrase.lower() in text_content:
                findings.append(ValidationFinding(
                    severity="ERROR",
                    validator_name=self.name,
                    message=f"Analysis mentions excluded contradictory concept: '{phrase}'",
                    path="classification",
                    fix_suggestion=f"Remove excluded concept '{phrase}'",
                ))
        return findings


class ActionabilityValidator:
    """Ensures actionable insights have clear directive verbs and targets."""
    name = "ActionabilityValidator"

    def validate(self, analysis: dict[str, Any]) -> list[ValidationFinding]:
        findings = []
        actions = analysis.get("actionable_insights", []) or analysis.get("actions", [])
        for idx, action in enumerate(actions):
            action_text = action.get("text", "") if isinstance(action, dict) else str(action)
            if len(action_text.strip()) < 10:
                findings.append(ValidationFinding(
                    severity="WARNING",
                    validator_name=self.name,
                    message=f"Action item #{idx + 1} is too brief or vague",
                    path=f"actions[{idx}]",
                    fix_suggestion="Include explicit operational or technical direction",
                ))
        return findings


def validate_semantic_content(
    analysis: dict[str, Any],
    theme: dict[str, Any],
    classification: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Validate that analysis answers micro-topic questions and avoids cross-topic leakage."""
    if not analysis:
        return False, ["Analysis payload is empty"]

    text_content = " ".join([
        " ".join(analysis.get("facts", [])),
        " ".join(analysis.get("actionable_insights", [])),
        str(analysis.get("summary", "")),
        str(analysis.get("main_argument", "")),
    ]).lower()

    if not text_content.strip():
        return False, ["Analysis text content is empty; cannot satisfy semantic contract"]

    findings: list[ValidationFinding] = []
    findings.extend(QuestionCoverageValidator().validate(analysis, theme, text_content))
    findings.extend(SpecificityValidator().validate(analysis, theme, text_content))
    findings.extend(GenericnessValidator().validate(analysis, text_content))
    findings.extend(ContradictionValidator().validate(analysis, classification, text_content))
    findings.extend(ActionabilityValidator().validate(analysis))

    errors = [f.message for f in findings if f.severity == "ERROR"]
    return len(errors) == 0, errors
