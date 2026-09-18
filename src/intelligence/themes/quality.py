"""Theme quality, specificity, and sibling difference metrics."""

from __future__ import annotations

import json
import re
from typing import Any


def theme_fingerprint(theme: dict[str, Any]) -> str:
    """Fingerprint meaningful theme content while ignoring routing IDs."""
    meaningful = {
        key: theme.get(key)
        for key in (
            "objective",
            "questions",
            "retrieval_intent",
            "evidence",
            "output",
            "watch_items",
            "disambiguation_focus",
            "analysis_contract",
        )
        if theme.get(key) not in (None, "", [], {})
    }
    normalized = re.sub(r"\s+", " ", json.dumps(meaningful, sort_keys=True, ensure_ascii=True).lower()).strip()
    return normalized


def theme_tokens(theme: dict[str, Any], field: str) -> set[str]:
    value = theme.get(field, "")
    text = json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", text.lower())
        if token not in {"what", "should", "with", "from", "that", "this", "why", "does", "matter"}
    }


def theme_lexical_overlap(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Measure lexical overlap; this is intentionally not a semantic model."""
    fields = (
        "analysis_contract",
        "questions",
        "retrieval_intent",
        "evidence",
        "output",
        "watch_items",
        "disambiguation_focus",
    )
    overlaps = {}
    for field in fields:
        a, b = theme_tokens(left, field), theme_tokens(right, field)
        overlaps[field] = round(len(a & b) / max(1, len(a | b)), 3)
    score = round(sum(overlaps.values()) / len(fields), 3)
    return {"score": score, "fields": overlaps, "flag": score >= 0.85}


# Compatibility alias for older integrations.
theme_semantic_overlap = theme_lexical_overlap


def theme_specificity_score(theme: dict[str, Any]) -> float:
    fields = (
        "analysis_contract",
        "questions",
        "retrieval_intent",
        "evidence",
        "output",
        "watch_items",
        "disambiguation_focus",
    )
    populated = sum(bool(theme_tokens(theme, field)) for field in fields)
    specific = len(
        theme_tokens(theme, "retrieval_intent")
        | theme_tokens(theme, "watch_items")
        | theme_tokens(theme, "disambiguation_focus")
    )
    return round(min(1.0, populated / len(fields) * 0.6 + min(1.0, specific / 20) * 0.4), 3)


def theme_quality_score(theme: dict[str, Any]) -> float:
    """Score the distinct analytical contract rather than token count alone."""
    questions = theme_tokens(theme, "questions")
    retrieval = theme_tokens(theme, "retrieval_intent")
    evidence = theme_tokens(theme, "evidence")
    watch = theme_tokens(theme, "watch_items")
    analysis = theme_tokens(theme, "analysis_contract")
    dimensions = [questions, retrieval, evidence, watch, analysis]
    populated = sum(bool(value) for value in dimensions)
    distinct = len(retrieval | evidence | watch)
    return round(min(1.0, populated / 5 * 0.6 + min(1.0, distinct / 16) * 0.4), 3)


def theme_difference_score(theme: dict[str, Any], siblings: list[dict[str, Any]]) -> float:
    """Score how much a theme differs from its sibling themes using deterministic tokens."""
    if not siblings:
        return 1.0
    tokens = set().union(
        *(theme_tokens(theme, field) for field in ("retrieval_intent", "evidence", "watch_items", "disambiguation_focus"))
    )
    overlaps = []
    for sibling in siblings:
        other = set().union(
            *(
                theme_tokens(sibling, field)
                for field in ("retrieval_intent", "evidence", "watch_items", "disambiguation_focus")
            )
        )
        overlaps.append(len(tokens & other) / max(1, len(tokens | other)))
    return round(1.0 - max(overlaps), 3)


def is_generic_theme(theme: dict[str, Any]) -> bool:
    """Detect if a theme is a generic noun-substitution without specific analytical guidance."""
    questions = [str(q).lower().strip() for q in theme.get("questions", [])]
    generic_question_stems = {
        "what changed?",
        "why does it matter?",
        "what should we watch?",
        "what happened?",
    }
    if questions and all(q in generic_question_stems for q in questions):
        # If questions are purely the generic template with no retrieval intent or specific watch items:
        if not theme.get("retrieval_intent") and not theme.get("watch_items"):
            return True
    return False
