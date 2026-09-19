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


def check_theme_specificity_breakdown(theme: dict[str, Any]) -> dict[str, Any]:
    """Provide detailed deterministic scores for theme analytical specificity."""
    q_tokens = theme_tokens(theme, "questions")
    r_tokens = theme_tokens(theme, "retrieval_intent")
    e_tokens = theme_tokens(theme, "evidence")
    w_tokens = theme_tokens(theme, "watch_items")
    o_tokens = theme_tokens(theme, "output")

    question_spec = min(1.0, len(q_tokens) / 12.0)
    retrieval_spec = min(1.0, len(r_tokens) / 10.0) if r_tokens else 0.2
    evidence_spec = min(1.0, len(e_tokens) / 8.0) if e_tokens else 0.2
    watch_spec = min(1.0, len(w_tokens) / 8.0) if w_tokens else 0.2
    output_spec = min(1.0, len(o_tokens) / 6.0) if o_tokens else 0.3

    score = round(
        question_spec * 0.25 + retrieval_spec * 0.25 + evidence_spec * 0.20 + watch_spec * 0.15 + output_spec * 0.15,
        3,
    )
    return {
        "question_specificity": round(question_spec, 3),
        "retrieval_specificity": round(retrieval_spec, 3),
        "evidence_specificity": round(evidence_spec, 3),
        "watch_specificity": round(watch_spec, 3),
        "output_specificity": round(output_spec, 3),
        "specificity_score": score,
    }


def check_cross_theme_duplication(
    theme: dict[str, Any],
    other_themes: list[dict[str, Any]],
) -> list[str]:
    """Check for identical analytical contracts across unrelated micro-topics."""
    warnings: list[str] = []
    tid = theme.get("id") or theme.get("theme_id")
    mt = theme.get("micro_topic_id") or theme.get("micro_topic")
    t_q = sorted(str(q).strip().lower() for q in theme.get("questions", []))
    t_r = json.dumps(theme.get("retrieval_intent", {}), sort_keys=True)
    t_e = sorted(str(e).strip().lower() for e in (
        theme.get("evidence_requirements")
        or (theme.get("evidence", {}).get("required", []) if isinstance(theme.get("evidence"), dict) else [])
    ))

    for other in other_themes:
        other_id = other.get("id") or other.get("theme_id")
        other_mt = other.get("micro_topic_id") or other.get("micro_topic")
        if other_id == tid or (mt and other_mt and mt == other_mt):
            continue

        o_q = sorted(str(q).strip().lower() for q in other.get("questions", []))
        if t_q and o_q and t_q == o_q:
            warnings.append(f"Verbatim duplicate questions with theme {other_id} ({other_mt})")

        o_r = json.dumps(other.get("retrieval_intent", {}), sort_keys=True)
        if t_r != "{}" and t_r == o_r:
            warnings.append(f"Verbatim duplicate retrieval_intent with theme {other_id} ({other_mt})")

        o_e = sorted(str(e).strip().lower() for e in (
            other.get("evidence_requirements")
            or (other.get("evidence", {}).get("required", []) if isinstance(other.get("evidence"), dict) else [])
        ))
        if t_e and o_e and t_e == o_e:
            warnings.append(f"Verbatim duplicate evidence_requirements with theme {other_id} ({other_mt})")

    return warnings


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


def validate_theme_completeness(theme: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    """Validate machine-checkable completeness per Set E Section 5 contract.

    Returns (valid, errors, warnings).
    """
    errors: list[str] = []
    warnings: list[str] = []

    theme_id = theme.get("theme_id") or theme.get("id")
    if not theme_id:
        errors.append("Theme missing theme_id")

    version = theme.get("version")
    if not version:
        errors.append("Theme missing version")

    # Check micro_topic if not a generic fallback
    is_fallback = theme.get("id") == "domain-fallback" or theme.get("micro_topic") in {"any", "*"}
    if not is_fallback:
        micro_topic = theme.get("micro_topic_id") or theme.get("micro_topic")
        if not micro_topic:
            errors.append("Theme missing micro_topic_id")

    # Questions check: questions >= 1
    questions = theme.get("questions") or theme.get("primary_questions") or []
    if not questions:
        errors.append("Theme questions must contain at least 1 question")

    # Evidence requirements check: evidence_requirements >= 1
    evidence_reqs = theme.get("evidence_requirements")
    if not evidence_reqs and isinstance(theme.get("evidence"), dict):
        evidence_reqs = theme.get("evidence", {}).get("required", [])
    if not evidence_reqs:
        errors.append("Theme evidence_requirements must contain at least 1 requirement")

    # Significance rules check: significance_rules >= 1
    significance = theme.get("significance_rules")
    if not significance:
        errors.append("Theme missing significance_rules")
    elif isinstance(significance, dict) and not (significance.get("significant_if") or significance.get("insignificant_if")):
        errors.append("Theme significance_rules cannot be empty")

    # Stream rules check
    streams = theme.get("stream_rules") or theme.get("content_streams") or {}
    if not streams.get("news"):
        errors.append("Theme missing stream_rules.news")
    if not streams.get("video"):
        errors.append("Theme missing stream_rules.video")

    # No update policy check
    no_update = theme.get("no_update_policy")
    if not no_update:
        errors.append("Theme missing no_update_policy")

    # Generic check
    if is_generic_theme(theme):
        errors.append("Theme flagged as generic template")

    # Specificity warning
    spec_score = theme_specificity_score(theme)
    if spec_score < 0.2:
        warnings.append(f"Theme specificity score is low: {spec_score:.2f}")

    return len(errors) == 0, errors, warnings


def generate_theme_health_json(
    records: list[dict[str, Any]],
    themes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate machine-readable theme health report for monitoring and CI."""
    theme_by_mt = {
        (theme.get("domain"), theme.get("micro_topic_id") or theme.get("micro_topic")): theme
        for theme in themes
        if theme.get("micro_topic_id") or (theme.get("micro_topic") not in {"any", "*"})
    }

    valid_count = 0
    invalid_count = 0
    missing_count = 0
    details: list[dict[str, Any]] = []

    for record in records:
        mt_id = record.get("id")
        domain = record.get("domain")
        theme = theme_by_mt.get((domain, mt_id))
        if not theme:
            missing_count += 1
            details.append({
                "micro_topic_id": mt_id,
                "status": "MISSING",
                "errors": ["No bespoke theme found for micro-topic"],
            })
            continue

        ok, errors, warnings = validate_theme_completeness(theme)
        if ok:
            valid_count += 1
            status = "PASS"
        else:
            invalid_count += 1
            status = "FAIL"

        details.append({
            "micro_topic_id": mt_id,
            "theme_id": theme.get("id") or theme.get("theme_id"),
            "status": status,
            "errors": errors,
            "warnings": warnings,
            "specificity_score": theme_specificity_score(theme),
            "quality_score": theme_quality_score(theme),
        })

    return {
        "total_records": len(records),
        "valid_themes": valid_count,
        "invalid_themes": invalid_count,
        "missing_themes": missing_count,
        "coverage_percentage": round((len(records) - missing_count) / max(1, len(records)) * 100, 2),
        "health_status": "HEALTHY" if missing_count == 0 and invalid_count == 0 else "UNHEALTHY",
        "details": details,
    }
