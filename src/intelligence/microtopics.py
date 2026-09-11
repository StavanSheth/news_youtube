from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .identity import make_micro_topic_id
from .classification import KeywordClassifier
from .statuses import IntelligenceStatus
from .profiles import resolve_microtopic_profile


GENERIC_TERMS = {
    "ai", "model", "models", "technology", "research", "policy", "security", "systems",
    "application", "applications", "engineering", "infrastructure", "development", "commercial",
    "government", "program", "programs", "market", "markets", "strategy", "funding", "supply",
    "chains", "tools", "tooling", "platform", "platforms", "open", "source", "digital", "cloud",
}


def _words(value: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]{2,}", value.lower()) if word not in {"and", "the", "for", "with"}}


def _phrase_found(phrase: str, text: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(phrase.lower())}(?!\w)", text.lower()))


def _signal(value: Any, *, default_strength: str = "medium") -> dict[str, str]:
    if isinstance(value, dict):
        return {"phrase": str(value.get("phrase", "")).strip(), "strength": str(value.get("strength", default_strength)).lower()}
    return {"phrase": str(value).strip(), "strength": default_strength}


def score_micro_topic_chunk(chunk_text: str, classification: dict[str, Any]) -> dict[str, Any]:
    """Score one chunk using the already-authoritative classification signals."""
    positive = [str(value) for value in classification.get("positive_signals", classification.get("signals", []))]
    negative = [str(value) for value in classification.get("matched_negative_signals", classification.get("negative_signals", []))]
    result = KeywordClassifier.score(chunk_text, positive, negative)
    return {**result, "relevant": bool(result["matched_signals"] and not result["negative_signals"])}


def _profile_for(domain: str, micro_topic: str, profiles: dict[str, Any] | None) -> dict[str, Any]:
    profiles = profiles or {}
    defaults = dict(profiles.get("defaults", {}))
    domain_config = profiles.get("domains", {}).get(domain, {})
    merged = {**defaults, **{key: value for key, value in domain_config.items() if key != "overrides"}}
    merged.update(domain_config.get("overrides", {}).get(micro_topic, {}))
    return merged


def catalog(
    taxonomy: dict[str, Any], topics: list[dict[str, Any]], profiles: dict[str, Any] | None = None, matrix: dict[str, Any] | None = None, templates: dict[str, Any] | None = None, *, strict: bool = False,
) -> list[dict[str, Any]]:
    """Create a canonical Domain -> Topic -> Micro-topic catalog from configuration."""
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
            profile = _profile_for(domain, micro_topic, profiles)
            if matrix_records:
                matrix_aliases = [value for value in (record["name"], micro_topic.replace("-", " ")) if len(_words(str(value))) >= 2]
                matrix_profile = {
                    # The matrix's evaluation text is an analysis objective, never a classifier feature list.
                    "aliases": list(dict.fromkeys(matrix_aliases)),
                    "positive_signals": [{"phrase": f"{record['name']} {suffix}", "strength": "strong"} for suffix in ("release", "announcement", "deployment")],
                    "required_evidence": [record["required_evidence"]],
                    "source_hints": [part.strip() for part in record["resources"].split("+")],
                    "analysis_contract": {"objective": record["evaluation"], "important_output": record["important_output"]},
                    "profile_origin": "derived",
                }
                profile = {**matrix_profile, **profile, "analysis_contract": {**matrix_profile["analysis_contract"], **profile.get("analysis_contract", {})}}
            template_id = record.get("template", "technology_capability")
            if templates:
                explicit = ((profiles or {}).get("domains", {}).get(domain, {}).get("overrides", {}).get(micro_topic, {})) if profiles is not None else {}
                semantic = matrix_profile if matrix_records else {}
                profile = resolve_microtopic_profile(micro_topic, domain=domain, topic=domain_topic.get("name", domain), template_id=template_id, templates=templates, explicit=explicit, semantic_override=semantic, enabled=profile.get("enabled", domain_topic.get("enabled", True)))
            elif profiles is not None and profiles.get("domains", {}).get(domain, {}).get("overrides", {}).get(micro_topic):
                profile["profile_origin"] = "explicit"
            # Production profiles must opt into evidence signals. The legacy
            # two-argument API keeps its derived alias behavior for callers
            # that have not loaded the Phase 2 profile overlay yet.
            explicit = bool(profile.get("aliases") or profile.get("positive_signals"))
            aliases = profile.get("aliases", [micro_topic.replace("-", " ")]) if profiles is None else profile.get("aliases", [])
            if profiles is not None and not explicit:
                aliases = [micro_topic.replace("-", " ")]
            aliases = [alias for alias in aliases if _words(str(alias)) - GENERIC_TERMS]
            if strict and not explicit and profile.get("enabled", domain_topic.get("enabled", True)):
                raise ValueError(f"Enabled micro-topic lacks explicit production profile: {domain}:{micro_topic}")
            entries.append(
                {
                    "domain": domain,
                    "topic": domain_topic.get("name", domain.replace("-", " ").title()),
                    "topic_key": domain_topic.get("key", domain),
                    "micro_topic": micro_topic,
                    "micro_topic_id": make_micro_topic_id(domain, domain_topic.get("key", domain), micro_topic),
                    "aliases": list(dict.fromkeys([*aliases, micro_topic.replace("-", " ")] if profiles is None else aliases)),
                    "positive_signals": [_signal(value, default_strength="strong") for value in profile.get("positive_signals", []) if _signal(value).get("phrase")],
                    "negative_signals": [_signal(value) for value in profile.get("negative_signals", []) if _signal(value).get("phrase")],
                    "disambiguators": list(profile.get("disambiguators", [])),
                    "exclusion_rules": list(profile.get("exclusion_rules", [])),
                    "entity_signals": list(profile.get("entity_signals", [])),
                    "event_signals": list(profile.get("event_signals", [])),
                    "secondary_threshold": float(profile.get("secondary_threshold", profile.get("classification_threshold", 0.25 if profiles is None else 0.5))),
                    "primary_threshold": float(profile.get("primary_threshold", profile.get("classification_threshold", 0.25 if profiles is None else 0.5))),
                    "max_secondary": int(profile.get("max_secondary", 1)),
                    "runner_up_margin": float(profile.get("runner_up_margin", 0.05)),
                    "classification_threshold": float(profile.get("classification_threshold", 0.25 if profiles is None else 0.5)),
                    "priority": profile.get("priority", domain_topic.get("priority", 5)),
                    "enabled": profile.get("enabled", domain_topic.get("enabled", True)),
                    "profile": {**profile, "profile_origin": profile.get("profile_origin", "explicit" if explicit else "derived")},
                    "profile_origin": profile.get("profile_origin", "explicit" if explicit else "derived"),
                    "profile_id": profile.get("profile_id", f"{domain}.{micro_topic}"),
                    "template_id": profile.get("template_id", template_id),
                }
            )
    return entries


def validate_microtopic_coverage(entries: list[dict[str, Any]], *, strict: bool = False) -> dict[str, Any]:
    """Return explicit/derived profile coverage and optionally fail production startup."""
    derived = [entry for entry in entries if entry.get("profile_origin") == "derived" and entry.get("enabled", True)]
    report = {"total": len(entries), "enabled": sum(bool(entry.get("enabled", True)) for entry in entries), "explicit": len(entries) - len(derived), "derived": len(derived), "missing": 0, "derived_ids": [entry["micro_topic_id"] for entry in derived]}
    if strict and derived:
        raise ValueError(f"Enabled micro-topics use derived profiles: {', '.join(report['derived_ids'])}")
    return report


def classify_micro_topics(item: dict[str, Any], entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Classify only micro-topics with independent, explainable evidence."""
    title_lower = str(item.get("title", "")).lower()
    body_lower = str(item.get("text", "")).lower()
    text_lower = f"{title_lower}\n{body_lower}"
    candidates: list[dict[str, Any]] = []
    for entry in entries:
        if not entry["enabled"]:
            continue
        positive_phrases = [{"phrase": alias, "strength": "strong"} for alias in entry.get("aliases", [])] + list(entry.get("positive_signals", []))
        scored = KeywordClassifier.score(text_lower, positive_phrases, list(entry.get("negative_signals", [])), title=title_lower)
        signals = scored["matched_signals"]
        negative = scored["negative_signals"]
        score = scored["score"]
        threshold = float(entry.get("primary_threshold", entry.get("classification_threshold", 0.5)))
        if signals and score >= float(entry.get("secondary_threshold", threshold)):
            candidates.append({
                **entry,
                "signals": signals,
                "positive_signals": signals,
                "matched_negative_signals": negative,
                "classification_score": round(score, 3),
                "negative_penalty": scored["negative_penalty"],
                "contradiction_penalty": scored["contradiction_penalty"],
                "confidence_method": "heuristic_weighted_signal_score",
                "classification_reason": f"matched {', '.join(signals)}" + (f"; excluded by {', '.join(negative)}" if negative else ""),
                "topic_id": entry["topic_key"],
                "analysis_contract": entry["profile"].get("analysis_contract", {}),
            })
    candidates.sort(key=lambda match: (-match["classification_score"], str(match["micro_topic"])))
    if not candidates:
        return []
    primary = candidates[0]
    runner_up = candidates[1]["classification_score"] if len(candidates) > 1 else 0.0
    margin = round(primary["classification_score"] - runner_up, 3)
    primary_threshold = float(primary.get("primary_threshold", primary.get("classification_threshold", 0.5)))
    if primary["classification_score"] < primary_threshold:
        return []
    selected = []
    for index, candidate in enumerate(candidates):
        if index == 0:
            status = "PRIMARY"
        elif len(selected) - 1 >= int(primary.get("max_secondary", 1)):
            continue
        elif candidate["classification_score"] < float(candidate.get("secondary_threshold", 0.5)) or margin < float(primary.get("runner_up_margin", 0.05)):
            continue
        else:
            status = "SECONDARY"
        specificity = min(1.0, sum(max(1, len(str(signal).split())) for signal in candidate["signals"]) / 12)
        confidence = round(max(0.0, min(1.0, 0.45 * candidate["classification_score"] + 0.25 * min(1.0, margin / 0.3) + 0.2 * specificity + 0.1 * (1.0 - candidate["contradiction_penalty"]))), 3)
        candidate.update({"classification_status": status, "primary_score": primary["classification_score"], "runner_up_score": runner_up, "margin": margin, "classification_confidence": confidence, "confidence": confidence})
        selected.append(candidate)
    return selected


def evaluate_micro_topic_status(assignments: list[dict[str, Any]], evaluation: dict[str, Any]) -> str:
    """Return a truthful final state for one completed micro-topic evaluation."""
    if any(item.get("source_status") == IntelligenceStatus.SOURCE_FAILURE.value for item in assignments):
        return IntelligenceStatus.SOURCE_FAILURE.value
    if any(item.get("retrieval_status") == IntelligenceStatus.RETRIEVAL_FAILURE.value for item in assignments):
        return IntelligenceStatus.RETRIEVAL_FAILURE.value
    if any(item.get("analysis_status") == IntelligenceStatus.ANALYSIS_FAILURE.value for item in assignments):
        return IntelligenceStatus.ANALYSIS_FAILURE.value
    if any(item.get("budget_skipped") for item in assignments):
        return IntelligenceStatus.BUDGET_SKIPPED.value
    if assignments and any("evidence_available" in item and not item.get("evidence_available") for item in assignments) and not evaluation:
        return IntelligenceStatus.INSUFFICIENT_EVIDENCE.value
    if evaluation.get("evaluation_status") != "EVALUATION_COMPLETE":
        return IntelligenceStatus.INSUFFICIENT_EVIDENCE.value
    if not assignments or not any(item.get("evidence_available", bool(item.get("relevant_count", 0) or item.get("evidence_count", 0))) for item in assignments):
        return IntelligenceStatus.NO_RELEVANT_CONTENT.value
    maximum = max(float(item.get("importance_score", 0)) for item in assignments)
    if maximum >= 75:
        return IntelligenceStatus.MAJOR_UPDATE.value
    if any(item.get("material_change", False) for item in assignments):
        return IntelligenceStatus.MINOR_UPDATE.value
    return IntelligenceStatus.NO_MAJOR_UPDATE.value


def coverage(entries: list[dict[str, Any]], assignments: list[dict[str, Any]], source_health: dict[str, Any]) -> list[dict[str, Any]]:
    """Report evaluated coverage without treating unchecked leaves as no update."""
    assigned: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for assignment in assignments:
        assigned[(assignment["domain"], assignment["micro_topic"])].append(assignment)
    ledger = source_health.get("evaluation_ledger", {})
    rows = []
    for entry in entries:
        evidence = assigned[(entry["domain"], entry["micro_topic"])]
        evaluation_key = f"{entry['domain']}:{entry['micro_topic']}"
        evaluation = ledger.get(evaluation_key, {})
        if evidence and not evaluation and any(item.get("evidence_available", bool(item.get("relevant_count", 0) or item.get("evidence_count", 0))) for item in evidence):
            evaluation = {"evaluation_status": "EVALUATION_COMPLETE"}
        checked = evaluation.get("evaluation_status") == "EVALUATION_COMPLETE"
        if not checked:
            checked = evaluation_key in source_health.get("evaluated_micro_topics", [])
            evaluation = {**evaluation, "evaluation_status": "EVALUATION_COMPLETE" if checked else "NOT_STARTED"}
        searched = checked
        status = evaluate_micro_topic_status(evidence, evaluation)
        candidate_count = sum(int(item.get("candidate_count", 0)) for item in evidence)
        relevant_count = sum(int(item.get("relevant_count", 0)) for item in evidence)
        event_count = sum(int(item.get("event_count", 0)) for item in evidence)
        publishable_count = sum(int(item.get("publishable_count", 0)) for item in evidence)
        rows.append({
            "domain": entry["domain"], "topic": entry["topic"], "micro_topic": entry["micro_topic"],
            "status": status, "searched": searched, "candidate_count": candidate_count,
            "relevant_count": relevant_count, "event_count": event_count,
            "publishable_count": publishable_count, "evidence_count": len(evidence),
        })
    return rows
