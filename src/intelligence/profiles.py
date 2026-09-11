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
    resolved = _merge(template, override or {})
    resolved.update({
        "profile_id": f"{domain}.{micro_topic}",
        "template_id": template_id,
        "domain": domain,
        "topic": topic,
        "micro_topic": micro_topic,
        "enabled": enabled,
        "resolution_level": "micro_topic" if override else "template",
        "fallback_used": False,
    })
    return resolved


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
        generated.append({
            "id": f"matrix-{record['domain']}-{record['id']}",
            "domain": record["domain"],
            "topic": "any",
            "micro_topic": record["id"],
            "priority": 5,
            "questions": analysis.get("questions", ["what_changed", "why_it_matters"]),
            "evidence": evidence,
            "output": output,
            "analysis_contract": {
                "objective": record.get("evaluation", ""),
                "questions": analysis.get("questions", []),
                "important_output": record.get("important_output", ""),
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
        "template_derived_profiles": sum(bool(entry.get("template_id")) for entry in entries),
        "exact_theme_records": exact,
        "theme_coverage_percent": round(exact / max(1, len(entries)) * 100, 2),
    }
