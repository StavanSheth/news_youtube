from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .identity import make_micro_topic_id
from .statuses import IntelligenceStatus


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


def _profile_for(domain: str, micro_topic: str, profiles: dict[str, Any] | None) -> dict[str, Any]:
    profiles = profiles or {}
    defaults = dict(profiles.get("defaults", {}))
    domain_config = profiles.get("domains", {}).get(domain, {})
    merged = {**defaults, **{key: value for key, value in domain_config.items() if key != "overrides"}}
    merged.update(domain_config.get("overrides", {}).get(micro_topic, {}))
    return merged


def catalog(
    taxonomy: dict[str, Any], topics: list[dict[str, Any]], profiles: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Create a canonical Domain -> Topic -> Micro-topic catalog from configuration."""
    configured = {topic.get("key"): topic for topic in topics}
    entries: list[dict[str, Any]] = []
    for domain, definition in taxonomy.get("domains", {}).items():
        domain_topic = configured.get(domain, {})
        for micro_topic in definition.get("topics", []):
            profile = _profile_for(domain, micro_topic, profiles)
            # Production profiles must opt into evidence signals. The legacy
            # two-argument API keeps its derived alias behavior for callers
            # that have not loaded the Phase 2 profile overlay yet.
            explicit = bool(profile.get("aliases") or profile.get("positive_signals"))
            aliases = profile.get("aliases", [micro_topic.replace("-", " ")]) if profiles is None else profile.get("aliases", [])
            if profiles is not None and not explicit:
                aliases = [micro_topic.replace("-", " ")]
            aliases = [alias for alias in aliases if _words(str(alias)) - GENERIC_TERMS]
            entries.append(
                {
                    "domain": domain,
                    "topic": domain_topic.get("name", domain.replace("-", " ").title()),
                    "topic_key": domain_topic.get("key", domain),
                    "micro_topic": micro_topic,
                    "micro_topic_id": make_micro_topic_id(domain, domain_topic.get("key", domain), micro_topic),
                    "aliases": list(dict.fromkeys([*aliases, micro_topic.replace("-", " ")] if profiles is None else aliases)),
                    "positive_signals": list(profile.get("positive_signals", [])),
                    "negative_signals": list(profile.get("negative_signals", [])),
                    "classification_threshold": float(profile.get("classification_threshold", 0.5)),
                    "priority": profile.get("priority", domain_topic.get("priority", 5)),
                    "enabled": profile.get("enabled", domain_topic.get("enabled", True)),
                    "profile": {**profile, "profile_origin": "explicit" if explicit else "derived"},
                    "profile_origin": "explicit" if explicit else "derived",
                }
            )
    return entries


def classify_micro_topics(item: dict[str, Any], entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Classify only micro-topics with independent, explainable evidence."""
    text = f"{item.get('title', '')}\n{item.get('text', '')}"
    text_lower = text.lower()
    matches: list[dict[str, Any]] = []
    for entry in entries:
        if not entry["enabled"]:
            continue
        positive_phrases = list(entry.get("aliases", [])) + list(entry.get("positive_signals", []))
        signals = sorted({phrase for phrase in positive_phrases if phrase and _phrase_found(phrase, text_lower)})
        negative = sorted({phrase for phrase in entry.get("negative_signals", []) if _phrase_found(phrase, text_lower)})
        direct = [phrase for phrase in signals if phrase in entry.get("aliases", [])]
        score = min(1.0, len(direct) * 0.35 + len(signals) * 0.2 - len(negative) * 0.25)
        threshold = float(entry.get("classification_threshold", 0.5))
        if signals and score >= threshold and not (negative and score < threshold + 0.2):
            confidence = round(max(0.0, min(1.0, score)), 3)
            matches.append({
                **entry,
                "signals": signals,
                "positive_signals": signals,
                "matched_negative_signals": negative,
                "confidence": round(confidence, 3),
                "classification_score": confidence,
                "classification_confidence": confidence,
                "classification_reason": f"matched {', '.join(signals)}" + (f"; excluded by {', '.join(negative)}" if negative else ""),
                "topic_id": entry["topic_key"],
                "analysis_contract": entry["profile"].get("analysis_contract", {}),
            })
    return sorted(matches, key=lambda match: (-match["classification_score"], str(match["micro_topic"])))


def coverage(entries: list[dict[str, Any]], assignments: list[dict[str, Any]], source_health: dict[str, Any]) -> list[dict[str, Any]]:
    """Report evaluated coverage without treating unchecked leaves as no update."""
    assigned: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for assignment in assignments:
        assigned[(assignment["domain"], assignment["micro_topic"])].append(assignment)
    healthy = bool(source_health.get("healthy_sources", 0))
    checked = bool(source_health.get("evaluated_micro_topics") or source_health.get("evaluated"))
    rows = []
    for entry in entries:
        evidence = assigned[(entry["domain"], entry["micro_topic"])]
        searched = bool(source_health.get("healthy_sources", 0) or source_health.get("checked_sources", 0))
        if evidence and any(item.get("source_status") == "SOURCE_FAILURE" for item in evidence):
            status = IntelligenceStatus.SOURCE_FAILURE.value
        elif evidence and any(item.get("retrieval_status") == "RETRIEVAL_FAILURE" for item in evidence):
            status = IntelligenceStatus.RETRIEVAL_FAILURE.value
        elif evidence and any(item.get("analysis_status") == "ANALYSIS_FAILURE" for item in evidence):
            status = IntelligenceStatus.ERROR.value
        elif evidence and any(item.get("budget_skipped") for item in evidence):
            status = IntelligenceStatus.BUDGET_SKIPPED.value
        elif evidence and not any(item.get("evidence_available", True) for item in evidence):
            status = IntelligenceStatus.INSUFFICIENT_EVIDENCE.value
        elif evidence:
            maximum = max(item.get("importance_score", 0) for item in evidence)
            status = IntelligenceStatus.MAJOR_UPDATE.value if maximum >= 75 else IntelligenceStatus.UPDATE.value if maximum >= 45 else IntelligenceStatus.MINOR_UPDATE.value
        elif checked and healthy:
            status = IntelligenceStatus.NO_RELEVANT_CONTENT.value
        else:
            status = IntelligenceStatus.INSUFFICIENT_EVIDENCE.value
        candidate_count = sum(int(item.get("candidate_count", 1)) for item in evidence)
        relevant_count = sum(int(item.get("relevant_count", 1)) for item in evidence)
        event_count = sum(int(item.get("event_count", 1)) for item in evidence)
        publishable_count = sum(int(item.get("publishable_count", 0)) for item in evidence)
        rows.append({
            "domain": entry["domain"], "topic": entry["topic"], "micro_topic": entry["micro_topic"],
            "status": status, "searched": searched, "candidate_count": candidate_count,
            "relevant_count": relevant_count, "event_count": event_count,
            "publishable_count": publishable_count, "evidence_count": len(evidence),
        })
    return rows
