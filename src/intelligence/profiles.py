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
        groups[group].append({"phrase": phrase, "strength": "strong" if len(phrase.split()) >= 3 else "medium"})
    groups = {name: values for name, values in groups.items() if values}
    explicit_signals = explicit.get("positive_signals", [])
    if explicit_signals:
        groups.setdefault("explicit", []).extend(explicit_signals)
    positive = [signal for values in groups.values() for signal in values]
    required_groups = ["explicit"] if explicit_signals else list(groups)
    return {
        "aliases": [name] if len(name.split()) >= 2 else [],
        "positive_signals": positive,
        "signal_groups": groups,
        "required_signal_groups": required_groups,
        "minimum_signal_groups": 1,
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
    resolved.update({
        "profile_id": f"{domain}.{micro_topic_id}", "template_id": template_id,
        "domain": domain, "topic": topic, "micro_topic": micro_topic_id,
        "enabled": enabled, "profile_origin": origin,
        "resolution_level": "micro_topic" if explicit or semantic_override else "template",
        "fallback_used": False,
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
    return [*existing, *generated]


def coverage_report(entries: list[dict[str, Any]], themes: list[dict[str, Any]]) -> dict[str, Any]:
    exact = sum(1 for entry in entries if any(theme.get("domain") == entry.get("domain") and theme.get("micro_topic") == entry.get("micro_topic") for theme in themes))
    enabled = [entry for entry in entries if entry.get("enabled", True)]
    production_ready = [entry for entry in enabled if entry.get("positive_signals") and entry.get("analysis_contract") and entry.get("retrieval_intent") and entry.get("template_id")]
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
        "positive_signal_coverage": round(sum(bool(entry.get("positive_signals")) for entry in enabled) / max(1, len(enabled)) * 100, 2),
        "negative_signal_coverage": round(sum(bool(entry.get("negative_signals")) for entry in enabled) / max(1, len(enabled)) * 100, 2),
        "disambiguator_coverage": round(sum(bool(entry.get("disambiguators")) for entry in enabled) / max(1, len(enabled)) * 100, 2),
        "retrieval_intent_coverage": round(sum(bool(entry.get("retrieval_intent")) for entry in enabled) / max(1, len(enabled)) * 100, 2),
        "analysis_contract_coverage": round(sum(bool(entry.get("analysis_contract")) for entry in enabled) / max(1, len(enabled)) * 100, 2),
        "exact_theme_records": exact,
        "theme_coverage_percent": round(exact / max(1, len(entries)) * 100, 2),
        "theme_counts": {"exact": exact, "generated": len(generated_themes), "topic_fallback": sum(theme.get("resolution_level") == "topic_fallback" for theme in themes), "domain_fallback": sum(theme.get("resolution_level") == "domain_family" for theme in themes), "global_fallback": sum(theme.get("resolution_level") == "global_fallback" for theme in themes), "missing": len(entries) - exact},
    }
