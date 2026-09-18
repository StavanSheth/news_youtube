"""Schema validation for structured micro-topic model analysis."""

from __future__ import annotations

from typing import Any


def validate_analysis_schema(analysis: Any) -> tuple[bool, list[str]]:
    """Verify that analysis has valid JSON/dict structure, expected keys, and valid types."""
    errors = []
    if not isinstance(analysis, dict):
        return False, ["Analysis payload must be a dictionary"]

    # If analysis is empty dictionary (e.g. from failure or empty retrieval)
    if not analysis:
        return True, []

    # Check importance score if present
    if "importance_score" in analysis:
        score = analysis["importance_score"]
        if not isinstance(score, (int, float)) or not 0 <= score <= 100:
            errors.append(f"Invalid importance_score: {score}; must be numeric 0..100")

    # Check confidence score if present
    if "confidence_score" in analysis:
        conf = analysis["confidence_score"]
        if not isinstance(conf, (int, float)) or not 0 <= conf <= 100:
            errors.append(f"Invalid confidence_score: {conf}; must be numeric 0..100")

    # Check facts or findings list
    facts = analysis.get("facts")
    if facts is not None and not isinstance(facts, list):
        errors.append("Field 'facts' must be a list of statements")

    # Check evidence references
    evidence = analysis.get("evidence")
    if evidence is not None and not isinstance(evidence, list):
        errors.append("Field 'evidence' must be a list of evidence citations")

    # Check actionable insights
    insights = analysis.get("actionable_insights")
    if insights is not None and not isinstance(insights, list):
        errors.append("Field 'actionable_insights' must be a list")

    return len(errors) == 0, errors
