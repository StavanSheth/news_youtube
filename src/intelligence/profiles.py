"""Deterministic reusable profile-template resolution."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


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
    return {
        "taxonomy_records": len(entries),
        "resolved_profiles": sum(bool(entry.get("profile_id")) for entry in entries),
        "profile_coverage_percent": round(sum(bool(entry.get("profile_id")) for entry in entries) / max(1, len(entries)) * 100, 2),
        "explicit_profiles": sum(entry.get("profile_origin") == "explicit" for entry in entries),
        "template_derived_profiles": sum(entry.get("profile_origin") in {"template", "derived"} for entry in entries),
        "exact_theme_records": exact,
        "theme_coverage_percent": round(exact / max(1, len(entries)) * 100, 2),
    }
