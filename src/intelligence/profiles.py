"""Deterministic reusable profile-template resolution."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


_GENERIC_SIGNAL_WORDS = {
    "new", "important", "major", "change", "changes", "latest", "update", "updates", "and", "the", "with",
    "if", "available", "actual", "result", "results", "impact", "implications", "significance", "evidence",
}


def profile_quality(profile: dict[str, Any]) -> dict[str, Any]:
    """Score profile quality from specificity and coverage, not profile existence."""
    signals = list(profile.get("positive_signals", []))
    phrases = [str(value.get("phrase", value) if isinstance(value, dict) else value) for value in signals]
    specific = [value for value in phrases if len(value.split()) >= 2 and not all(word in _GENERIC_SIGNAL_WORDS for word in value.split())]
    specificity = min(1.0, len(specific) / 4)
    signal_quality = min(1.0, len(set(phrases)) / 5)
    negative = profile.get("negative_signals", [])
    negative_quality = min(1.0, sum(len(str(value.get("phrase", value) if isinstance(value, dict) else value).split()) >= 2 for value in negative) / 2)
    disambiguation = min(1.0, len(profile.get("disambiguators", [])) / 3)
    evidence = min(1.0, len(profile.get("required_evidence", profile.get("evidence", {}).get("required", []))) / 2)
    theme = min(1.0, bool(profile.get("analysis_contract")) + bool(profile.get("retrieval_intent")))
    score = round(0.25 * specificity + 0.2 * signal_quality + 0.15 * negative_quality + 0.15 * disambiguation + 0.15 * evidence + 0.1 * theme, 3)
    return {"specificity": round(specificity, 3), "signal_quality": round(signal_quality, 3), "negative_signal_quality": round(negative_quality, 3), "disambiguation_quality": round(disambiguation, 3), "evidence_quality": round(evidence, 3), "theme_quality": round(theme, 3), "profile_completeness_score": score, "profile_quality_score": score, "classification_validation_score": None, "benchmark_status": "UNDER_TESTED"}


def _semantic_phrases(*values: str) -> list[str]:
    phrases: list[str] = []
    single_terms: list[str] = []
    for value in values:
        for raw in re.split(r"[,;/+|]", str(value or "")):
            phrase = re.sub(r"\s+", " ", raw.strip().lower())
            words = [word for word in re.findall(r"[a-z0-9][a-z0-9.-]*", phrase) if word not in _GENERIC_SIGNAL_WORDS]
            if len(words) == 1 and len(words[0]) >= 5:
                single_terms.append(words[0])
            if len(words) >= 2 and len(" ".join(words)) >= 8:
                normalized = " ".join(words)
                if normalized not in phrases:
                    phrases.append(normalized)
    for left, right in zip(single_terms, single_terms[1:]):
        phrase = f"{left} {right}"
        if phrase not in phrases:
            phrases.append(phrase)
    return phrases[:12]


def compile_semantic_profile(record: dict[str, Any], template: dict[str, Any], explicit: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compile matrix semantics into reusable signal groups and contracts."""
    explicit = explicit or {}
    name = str(record.get("name", record.get("id", ""))).strip()
    phrases = _semantic_phrases(
        record.get("evaluation", ""), record.get("required_evidence", ""),
        record.get("important_output", ""), record.get("resources", ""),
    )
    group_names = ("capability", "architecture", "deployment", "evidence")
    groups: dict[str, list[dict[str, str]]] = {group: [] for group in group_names}
    for phrase in phrases:
        lowered = phrase
        if any(term in lowered for term in ("architecture", "algorithm", "method", "system", "design")):
            group = "architecture"
        elif any(term in lowered for term in ("deployment", "serving", "latency", "cost", "capacity", "infrastructure", "production")):
            group = "deployment"
        elif any(term in lowered for term in ("evidence", "benchmark", "validation", "model card", "official", "paper")):
            group = "evidence"
        else:
            group = "capability"
        groups[group].append({
            "phrase": phrase,
            "strength": "strong" if len(phrase.split()) >= 3 else "medium",
            "type": "positive",
            "specificity": "specific" if len(phrase.split()) >= 2 else "broad",
            "source": "matrix_semantics",
        })
    groups = {name: values for name, values in groups.items() if values}
    explicit_signals = explicit.get("positive_signals", [])
    if explicit_signals:
        groups.setdefault("explicit", []).extend([
            value if isinstance(value, dict) else {"phrase": str(value), "strength": "strong", "type": "positive", "specificity": "specific", "source": "curated_override"}
            for value in [*explicit.get("aliases", []), *explicit_signals]
        ])
    positive = [signal for values in groups.values() for signal in values]
    required_groups = explicit.get("required_signal_groups") or (["explicit"] if explicit_signals else list(groups))
    minimum_groups = int(explicit.get("minimum_signal_groups", 1))
    group_policy = explicit.get("group_policy", {"mode": "AT_LEAST_N", "minimum": minimum_groups, "groups": required_groups})
    return {
        "aliases": [name] if len(name.split()) >= 2 else [],
        "positive_signals": positive,
        "signal_groups": groups,
        "required_signal_groups": required_groups,
        "minimum_signal_groups": minimum_groups,
        "group_policy": group_policy,
        "disambiguators": _semantic_phrases(record.get("important_output", ""), record.get("required_evidence", ""))[:4],
        "entity_signals": _semantic_phrases(record.get("resources", ""))[:4],
        "event_signals": _semantic_phrases(record.get("evaluation", ""))[:4],
        "retrieval_intent": {
            "required_concepts": [name],
            "preferred_source_types": str(record.get("resources", "")).split("+"),
            "evidence_types": [record.get("required_evidence", "")],
            "exclusion_concepts": explicit.get("negative_signals", []),
            "freshness": template.get("retrieval", {}).get("freshness", "30d"),
        },
        "profile_quality": profile_quality({"positive_signals": positive, "negative_signals": explicit.get("negative_signals", []), "disambiguators": explicit.get("disambiguators", []), "required_evidence": [record.get("required_evidence", "")], "analysis_contract": record.get("important_output"), "retrieval_intent": True}),
    }


def resolve_microtopic_profile(
    micro_topic_id: str,
    *,
    domain: str,
    topic: str,
    template_id: str,
    templates: dict[str, Any],
    explicit: dict[str, Any] | None = None,
    semantic_override: dict[str, Any] | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    """Resolve one profile and make its provenance explicit."""
    available = templates.get("templates", templates)
    if template_id not in available:
        raise ValueError(f"Unknown profile template: {template_id}")
    explicit = explicit or {}
    semantic_override = semantic_override or {}
    resolved = _merge(available[template_id], semantic_override)
    resolved = _merge(resolved, explicit)
    origin = "explicit" if explicit else ("derived" if semantic_override else "template")
    origin_code = "CURATED" if explicit else ("MATRIX_DERIVED" if semantic_override else "TEMPLATE_DERIVED")
    status = "PRODUCTION_READY" if explicit else "UNDER_TEST"
    resolved.update({
        "profile_id": f"{domain}.{micro_topic_id}", "template_id": template_id,
        "domain": domain, "topic": topic, "micro_topic": micro_topic_id,
        "enabled": enabled, "profile_origin": origin,
        "profile_origin_code": origin_code,
        "production_status": status,
        "resolution_level": "micro_topic" if explicit or semantic_override else "template",
        "fallback_used": False,
        "profile_quality": profile_quality(resolved),
    })
    return resolved


def resolve_profile(
    domain: str,
    topic: str,
    micro_topic: str,
    template_id: str,
    templates: dict[str, Any],
    override: dict[str, Any] | None = None,
    *,
    enabled: bool = True,
) -> dict[str, Any]:
    available = templates.get("templates", templates)
    template = available.get(template_id)
    if not template:
        raise ValueError(
            f"Profile resolution failed: domain={domain} topic={topic} "
            f"micro_topic={micro_topic} template={template_id} reason=unknown template"
        )
    return resolve_microtopic_profile(micro_topic, domain=domain, topic=topic, template_id=template_id, templates=templates, explicit=override, enabled=enabled)


def build_matrix_themes(
    records: list[dict[str, Any]],
    templates: dict[str, Any],
    existing: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create exact, template-backed themes only where YAML has no exact override."""
    available = templates.get("templates", templates)
    existing_keys = {
        (theme.get("domain", "all"), theme.get("micro_topic", "any"))
        for theme in existing
        if theme.get("micro_topic", "any") not in {"any", "*"}
    }
    generated = []
    for record in records:
        key = (record.get("domain"), record.get("id"))
        if key in existing_keys:
            continue
        template = available.get(record.get("template", "technology_capability"), {})
        analysis = template.get("analysis", {})
        evidence = template.get("evidence", {})
        output = template.get("output", {})
        name = str(record.get("name", record.get("id", ""))).strip()
        important = str(record.get("important_output", "")).strip()
        generated.append({
            "id": f"matrix-{record['domain']}-{record['id']}",
            "domain": record["domain"],
            "topic": "any", "micro_topic_id": record["id"],
            "micro_topic": record["id"],
            "theme_name": f"{name} Intelligence",
            "priority": 5,
            "questions": [*analysis.get("questions", ["what_changed", "why_it_matters"]), f"what_changed_in_{record['id']}", f"what_to_watch_for_{record['id']}"],
            "evidence": {**evidence, "required": [*evidence.get("required", []), record.get("required_evidence", "")]},
            "output": {**output, "focus": important},
            "watch_items": [important, record.get("required_evidence", "")],
            "disambiguation_focus": [name, record.get("resources", "")],
            "retrieval_intent": {
                "required_concepts": [name], "preferred_source_types": str(record.get("resources", "")).split("+"),
                "evidence_types": [record.get("required_evidence", "")], "exclusion_concepts": [],
                "freshness": template.get("retrieval", {}).get("freshness", "30d"),
            },
            "analysis_contract": {
                "objective": f"Assess {name} specifically through its measurable change, evidence, and practical implications.",
                "questions": analysis.get("questions", []),
                "important_output": important,
            },
            "resolution_policy": "template_backed_exact",
        })
    curated = [{**theme, "theme_origin": theme.get("theme_origin", "CURATED")} for theme in existing]
    generated = [{**theme, "theme_origin": "DERIVED"} for theme in generated]
    return [_normalize_theme_contract(theme) for theme in [*curated, *generated]]


def _normalize_theme_contract(theme: dict[str, Any]) -> dict[str, Any]:
    """Give curated and derived themes one observable analytical contract shape.

    The source YAML stays concise; these values are deterministic runtime
    defaults assembled from fields it already owns.  Explicit contract fields
    always win over the generated defaults.
    """
    output = theme.get("output", {}) or {}
    evidence = theme.get("evidence", {}) or {}
    questions = list(theme.get("questions", []))
    defaults = {
        "objective": f"Assess {theme.get('micro_topic', theme.get('id', 'the change'))} using topic-specific evidence and implications.",
        "primary_questions": questions,
        "required_dimensions": list(output.get("sections", [])),
        "forbidden_dimensions": [],
        "decision_criteria": list(evidence.get("required", [])),
        "comparison_axes": [theme.get("domain", "all"), theme.get("topic", "any"), theme.get("micro_topic", "any")],
        "watch_indicators": list(theme.get("watch_items", [])),
        "actionability": output.get("report_type", output.get("report_types", [])),
    }
    explicit = theme.get("analysis_contract", {}) or {}
    return {**theme, "analysis_contract": {**defaults, **explicit}}


def coverage_report(entries: list[dict[str, Any]], themes: list[dict[str, Any]], benchmark: dict[str, Any] | None = None) -> dict[str, Any]:
    exact = sum(1 for entry in entries if any(theme.get("domain") == entry.get("domain") and theme.get("micro_topic") == entry.get("micro_topic") for theme in themes))
    enabled = [entry for entry in entries if entry.get("enabled", True)]
    benchmark_topics = (benchmark or {}).get("per_micro_topic", {})
    production_ready = [entry for entry in enabled if entry.get("positive_signals") and entry.get("analysis_contract") and entry.get("retrieval_intent") and entry.get("template_id") and entry.get("profile_quality", {}).get("profile_completeness_score", 0) >= 0.8 and benchmark_topics.get(entry.get("micro_topic"), {}).get("validation_state") == "VALIDATED"]
    def readiness(entry: dict[str, Any]) -> tuple[str, list[str]]:
        reasons: list[str] = []
        if not entry.get("positive_signals") or not entry.get("analysis_contract"):
            reasons.append("NOT_READY_PROFILE_INCOMPLETE")
        if entry.get("profile_quality", {}).get("profile_completeness_score", 0) < 0.8:
            reasons.append("NOT_READY_PROFILE_GENERIC")
        benchmark_row = benchmark_topics.get(entry.get("micro_topic"), {})
        if benchmark_row.get("validation_state") != "VALIDATED":
            reasons.append("NOT_READY_BENCHMARK_UNDER_SUPPORTED")
        return ("READY" if not reasons else "UNDER_TESTED", reasons)
    weak = [entry for entry in enabled if entry not in production_ready]
    exact_themes = [theme for theme in themes if theme.get("micro_topic") not in {None, "any", "*"}]
    generated_themes = [theme for theme in exact_themes if str(theme.get("id", "")).startswith("matrix-")]
    return {
        "taxonomy_records": len(entries), "total_micro_topics": len(enabled),
        "resolved_profiles": sum(bool(entry.get("profile_id")) for entry in entries),
        "profile_coverage_percent": round(sum(bool(entry.get("profile_id")) for entry in entries) / max(1, len(entries)) * 100, 2),
        "explicit_profiles": sum(entry.get("profile_origin") == "explicit" for entry in entries),
        "template_derived_profiles": sum(entry.get("profile_origin") in {"template", "derived"} for entry in entries),
        "production_ready_profiles": len(production_ready), "weak_profiles": len(weak), "missing_profiles": len(enabled) - len(production_ready) - len(weak),
        "profile_quality_threshold": 0.8,
        "profile_quality_below_threshold": [entry["micro_topic_id"] for entry in enabled if entry.get("profile_quality", {}).get("profile_quality_score", 0) < 0.8],
        "micro_topic_profiles": [{"micro_topic_id": entry["micro_topic_id"], "profile_origin": entry.get("profile_origin_code", entry.get("profile_origin")), "profile_quality": entry.get("profile_quality", {}), "signal_count": len(entry.get("positive_signals", [])) + len(entry.get("negative_signals", [])), "signal_group_count": len(entry.get("signal_groups", {})), "positive_signal_count": len(entry.get("positive_signals", [])), "negative_signal_count": len(entry.get("negative_signals", [])), "benchmark": benchmark_topics.get(entry.get("micro_topic"), {"validation_state": "UNDER_TESTED"}), "readiness_reasons": readiness(entry)[1], "production_eligibility": readiness(entry)[0]} for entry in enabled],
        "positive_signal_coverage": round(sum(bool(entry.get("positive_signals")) for entry in enabled) / max(1, len(enabled)) * 100, 2),
        "negative_signal_coverage": round(sum(bool(entry.get("negative_signals")) for entry in enabled) / max(1, len(enabled)) * 100, 2),
        "disambiguator_coverage": round(sum(bool(entry.get("disambiguators")) for entry in enabled) / max(1, len(enabled)) * 100, 2),
        "retrieval_intent_coverage": round(sum(bool(entry.get("retrieval_intent")) for entry in enabled) / max(1, len(enabled)) * 100, 2),
        "analysis_contract_coverage": round(sum(bool(entry.get("analysis_contract")) for entry in enabled) / max(1, len(enabled)) * 100, 2),
        "exact_theme_records": exact,
        "theme_coverage_percent": round(exact / max(1, len(entries)) * 100, 2),
        "theme_counts": {"exact": exact, "generated": len(generated_themes), "curated_exact": sum(theme.get("theme_origin") == "CURATED" and theme.get("micro_topic") not in {None, "any", "*"} for theme in themes), "derived_exact": sum(theme.get("theme_origin") == "DERIVED" and theme.get("micro_topic") not in {None, "any", "*"} for theme in themes), "topic_fallback": sum(theme.get("resolution_level") == "topic_fallback" for theme in themes), "domain_fallback": sum(theme.get("resolution_level") == "domain_family" for theme in themes), "global_fallback": sum(theme.get("resolution_level") == "global_fallback" for theme in themes), "controlled_fallback": sum(theme.get("resolution_level") == "controlled_fallback" for theme in themes), "missing": len(entries) - exact},
    }
