"""Canonical Domain -> Topic -> Micro-topic catalog builder."""

from __future__ import annotations

from typing import Any
from ..identity import make_micro_topic_id
from ..profiles import compile_semantic_profile, profile_quality, resolve_microtopic_profile
from .signals import GENERIC_TERMS, parse_signal, words
from .profiles import profile_for


def catalog(
    taxonomy: dict[str, Any] | None = None,
    topics: list[dict[str, Any]] | None = None,
    profiles: dict[str, Any] | None = None,
    matrix: dict[str, Any] | None = None,
    templates: dict[str, Any] | None = None,
    *,
    strict: bool = False,
) -> list[dict[str, Any]]:
    """Create a canonical Domain -> Topic -> Micro-topic catalog from configuration."""
    if taxonomy is None or topics is None:
        from ..infrastructure.config import load_application_config
        cfg = load_application_config()
        taxonomy = taxonomy if taxonomy is not None else cfg.taxonomy
        topics = topics if topics is not None else cfg.topics
        profiles = profiles if profiles is not None else cfg.microtopics
        matrix = matrix if matrix is not None else cfg.microtopic_matrix
        templates = templates if templates is not None else cfg.profile_templates
    configured = {topic.get("key"): topic for topic in topics}
    entries: list[dict[str, Any]] = []
    matrix_records = (matrix or {}).get("records", [])
    if matrix_records:
        domain_leaves = {
            domain: [record for record in matrix_records if record.get("domain") == domain]
            for domain in sorted({record.get("domain", "") for record in matrix_records})
        }
    else:
        domain_leaves = {
            domain: [{"id": micro_topic, "name": micro_topic.replace("-", " ")} for micro_topic in definition.get("topics", [])]
            for domain, definition in taxonomy.get("domains", {}).items()
        }
    for domain, leaves in domain_leaves.items():
        domain_topic = configured.get(domain, {})
        for record in leaves:
            micro_topic = record["id"]
            profile = profile_for(domain, micro_topic, profiles)
            if matrix_records:
                template_id = record.get("template", "technology_capability")
                template = ((templates or {}).get("templates", templates or {}).get(template_id, {}))
                explicit_override = ((profiles or {}).get("domains", {}).get(domain, {}).get("overrides", {}).get(micro_topic, {})) if profiles is not None else {}
                semantic_profile = compile_semantic_profile(record, template, explicit_override)
                matrix_profile = {
                    "aliases": semantic_profile["aliases"],
                    "positive_signals": semantic_profile["positive_signals"],
                    "signal_groups": semantic_profile["signal_groups"],
                    "required_signal_groups": semantic_profile["required_signal_groups"],
                    "minimum_signal_groups": semantic_profile["minimum_signal_groups"],
                    "group_policy": semantic_profile["group_policy"],
                    "disambiguators": semantic_profile["disambiguators"],
                    "entity_signals": semantic_profile["entity_signals"],
                    "event_signals": semantic_profile["event_signals"],
                    "retrieval_intent": semantic_profile["retrieval_intent"],
                    "required_evidence": [record["required_evidence"]],
                    "required_entities": list(profile.get("required_entities", [])),
                    "evaluation_dimensions": [part.strip() for part in str(record.get("evaluation", "")).split(",") if part.strip()],
                    "watch_indicators": [record.get("important_output", "")],
                    "theme_reference": record.get("id"),
                    "source_hints": [part.strip() for part in record["resources"].split("+")],
                    "analysis_contract": {"objective": record["evaluation"], "important_output": record["important_output"]},
                    "profile_origin": "derived",
                }
                profile = {**matrix_profile, **profile, "analysis_contract": {**matrix_profile["analysis_contract"], **profile.get("analysis_contract", {})}}
            template_id = record.get("template", "technology_capability")
            if templates:
                explicit = ((profiles or {}).get("domains", {}).get(domain, {}).get("overrides", {}).get(micro_topic, {})) if profiles is not None else {}
                semantic = matrix_profile if matrix_records else {}
                profile = resolve_microtopic_profile(
                    micro_topic,
                    domain=domain,
                    topic=domain_topic.get("name", domain),
                    template_id=template_id,
                    templates=templates,
                    explicit=explicit,
                    semantic_override=semantic,
                    enabled=profile.get("enabled", domain_topic.get("enabled", True)),
                )
            elif profiles is not None and profiles.get("domains", {}).get(domain, {}).get("overrides", {}).get(micro_topic):
                profile["profile_origin"] = "explicit"
                profile["profile_origin_code"] = "CURATED"

            profile_origin_code = str(profile.get("profile_origin_code", "MATRIX_DERIVED"))
            profile_is_curated = profile_origin_code == "CURATED"
            aliases = profile.get("aliases", [micro_topic.replace("-", " ")]) if profiles is None else profile.get("aliases", [])
            if profiles is not None and not profile.get("aliases"):
                aliases = [micro_topic.replace("-", " ")]
            aliases = [alias for alias in aliases if words(str(alias)) - GENERIC_TERMS]
            if strict and not profile_is_curated and profile.get("enabled", domain_topic.get("enabled", True)):
                raise ValueError(f"Enabled micro-topic is not curated for strict mode: {domain}:{micro_topic}")

            entries.append(
                {
                    "domain": domain,
                    "topic": domain_topic.get("name", domain.replace("-", " ").title()),
                    "topic_key": domain_topic.get("key", domain),
                    "micro_topic": micro_topic,
                    "micro_topic_id": make_micro_topic_id(domain, domain_topic.get("key", domain), micro_topic),
                    "aliases": list(dict.fromkeys([*aliases, micro_topic.replace("-", " ")] if profiles is None else aliases)),
                    "positive_signals": [parse_signal(value, default_strength="strong", default_type="positive") for value in profile.get("positive_signals", []) if parse_signal(value, default_type="positive").get("phrase")],
                    "negative_signals": [parse_signal(value) for value in profile.get("negative_signals", []) if parse_signal(value).get("phrase")],
                    "disambiguators": list(profile.get("disambiguators", [])),
                    "exclusion_rules": list(profile.get("exclusion_rules", [])),
                    "entity_signals": list(profile.get("entity_signals", [])),
                    "event_signals": list(profile.get("event_signals", [])),
                    "signal_groups": (
                        {**profile.get("signal_groups", {}), "explicit": [parse_signal(value, default_strength="strong", default_type="positive") for value in profile.get("positive_signals", [])]}
                        if profile.get("positive_signals") and "explicit" not in profile.get("signal_groups", {})
                        else profile.get("signal_groups", {})
                    ),
                    "required_signal_groups": list(profile.get("required_signal_groups", [])) if profile.get("signal_groups") else [],
                    "minimum_signal_groups": int(profile.get("minimum_signal_groups", 1)) if profile.get("signal_groups") else 0,
                    "group_policy": profile.get("group_policy", {"mode": "AT_LEAST_N", "minimum": int(profile.get("minimum_signal_groups", 1)), "groups": list(profile.get("required_signal_groups", []))}),
                    "secondary_threshold": float(profile.get("secondary_threshold", profile.get("classification_threshold", 0.25 if profiles is None else 0.5))),
                    "primary_threshold": float(profile.get("primary_threshold", profile.get("classification_threshold", 0.25 if profiles is None else 0.5))),
                    "max_secondary": int(profile.get("max_secondary", 1)),
                    "runner_up_margin": float(profile.get("runner_up_margin", 0.05)),
                    "classification_threshold": float(profile.get("classification_threshold", 0.25 if profiles is None else 0.5)),
                    "priority": profile.get("priority", domain_topic.get("priority", 5)),
                    "enabled": profile.get("enabled", domain_topic.get("enabled", True)),
                    "profile": {**profile, "profile_origin": profile.get("profile_origin", "explicit" if profile_is_curated else "derived")},
                    "retrieval_intent": profile.get("retrieval_intent", {}),
                    "analysis_contract": profile.get("analysis_contract", {}),
                    "profile_origin": profile.get("profile_origin", "explicit" if profile_is_curated else "derived"),
                    "profile_origin_code": profile_origin_code,
                    "profile_quality": profile.get("profile_quality", profile_quality(profile)),
                    "profile_id": profile.get("profile_id", f"{domain}.{micro_topic}"),
                    "template_id": profile.get("template_id", template_id),
                }
            )
    return entries


def validate_microtopic_coverage(entries: list[dict[str, Any]], *, strict: bool = False) -> dict[str, Any]:
    """Return explicit/derived profile coverage and optionally fail production startup."""
    derived = [entry for entry in entries if entry.get("profile_origin") == "derived" and entry.get("enabled", True)]
    report = {
        "total": len(entries),
        "enabled": sum(bool(entry.get("enabled", True)) for entry in entries),
        "explicit": len(entries) - len(derived),
        "derived": len(derived),
        "missing": 0,
        "derived_ids": [entry["micro_topic_id"] for entry in derived],
    }
    if strict and derived:
        raise ValueError(f"Enabled micro-topics use derived profiles: {', '.join(report['derived_ids'])}")
    return report
