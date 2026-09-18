"""Semantic validation ensuring alignment with micro-topic questions and contracts."""

from __future__ import annotations

from typing import Any


def validate_semantic_content(
    analysis: dict[str, Any],
    theme: dict[str, Any],
    classification: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Validate that analysis answers micro-topic questions and avoids cross-topic leakage."""
    errors = []
    if not analysis:
        return True, []

    text_content = " ".join([
        " ".join(analysis.get("facts", [])),
        " ".join(analysis.get("actionable_insights", [])),
        str(analysis.get("summary", "")),
        str(analysis.get("main_argument", "")),
    ]).lower()

    if not text_content.strip():
        return True, []

    # Check forbidden dimensions if defined in theme contract
    forbidden_dimensions = theme.get("analysis_contract", {}).get("forbidden_dimensions", [])
    for forbidden in forbidden_dimensions:
        if forbidden and forbidden.lower() in text_content:
            errors.append(f"Analysis contains forbidden dimension for theme: '{forbidden}'")

    # Check question alignment
    questions = theme.get("questions", [])
    if questions and len(text_content) < 30:
        errors.append("Analysis is too brief to address required theme questions")

    # Check for obvious contradictory signals if present in classification
    negative_signals = classification.get("profile", {}).get("negative_signals", [])
    for neg in negative_signals:
        phrase = (neg.get("phrase") if isinstance(neg, dict) else neg) or ""
        neg_type = (neg.get("type") if isinstance(neg, dict) else "")
        if neg_type == "exclusion" and phrase.lower() in text_content:
            errors.append(f"Analysis mentions excluded contradictory concept: '{phrase}'")

    return len(errors) == 0, errors
