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


def catalog(taxonomy: dict[str, Any], topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create a canonical Domain -> Topic -> Micro-topic catalog from configuration."""
    configured = {topic.get("key"): topic for topic in topics}
    entries: list[dict[str, Any]] = []
    for domain, definition in taxonomy.get("domains", {}).items():
        domain_topic = configured.get(domain, {})
        for micro_topic in definition.get("topics", []):
            # Topic-level aliases such as "AI" are intentionally not copied onto
            # every leaf; doing so would classify an article into the whole domain.
            aliases = [micro_topic.replace("-", " ")]
            entries.append(
                {
                    "domain": domain,
                    "topic": domain_topic.get("name", domain.replace("-", " ").title()),
                    "topic_key": domain_topic.get("key", domain),
                    "micro_topic": micro_topic,
                    "aliases": aliases,
                    "priority": domain_topic.get("priority", 5),
                    "enabled": domain_topic.get("enabled", True),
                }
            )
    return entries


def classify_micro_topics(item: dict[str, Any], entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Conservative lexical classifier retaining match evidence for every assignment."""
    text = f"{item.get('title', '')}\n{item.get('text', '')}"
    tokens = _words(text)
    matches: list[dict[str, Any]] = []
    for entry in entries:
        if not entry["enabled"]:
            continue
        target = _words(entry["micro_topic"])
        alias_terms = set().union(*(_words(alias) for alias in entry.get("aliases", [])))
        signals = sorted((target | alias_terms) & tokens)
        direct = target & tokens
        strong_direct = direct - GENERIC_TERMS
        # A generic domain alias alone is not enough to create a micro-topic assignment.
        strong_signals = set(signals) - GENERIC_TERMS
        if not strong_direct and len(strong_signals) < 2:
            continue
        confidence = min(1.0, (len(strong_direct) * 0.7 + len(strong_signals) * 0.15) / max(1, len(target - GENERIC_TERMS)))
        if confidence >= 0.25:
            matches.append({
                **entry,
                "micro_topic_id": make_micro_topic_id(entry["domain"], entry["topic"], entry["micro_topic"]),
                "signals": signals,
                "confidence": round(confidence, 3),
            })
    return sorted(matches, key=lambda match: (match["confidence"], match["priority"]), reverse=True)


def coverage(entries: list[dict[str, Any]], assignments: list[dict[str, Any]], source_health: dict[str, Any]) -> list[dict[str, Any]]:
    """Explicit coverage prevents empty collection from being presented as no update."""
    assigned: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for assignment in assignments:
        assigned[(assignment["domain"], assignment["micro_topic"])].append(assignment)
    healthy = bool(source_health.get("healthy_sources", 0))
    rows = []
    for entry in entries:
        evidence = assigned[(entry["domain"], entry["micro_topic"])]
        searched = bool(source_health.get("healthy_sources", 0) or source_health.get("checked_sources", 0))
        if evidence and any(item.get("source_status") == "SOURCE_FAILURE" for item in evidence):
            status = IntelligenceStatus.SOURCE_FAILURE.value
        elif evidence and any(item.get("retrieval_status") == "RETRIEVAL_FAILURE" for item in evidence):
            status = IntelligenceStatus.RETRIEVAL_FAILURE.value
        elif evidence and any(item.get("analysis_status") == "ANALYSIS_FAILURE" for item in evidence):
            status = IntelligenceStatus.ANALYSIS_FAILURE.value
        elif evidence and not any(item.get("evidence_available", True) for item in evidence):
            status = IntelligenceStatus.INSUFFICIENT_EVIDENCE.value
        elif evidence:
            maximum = max(item.get("importance_score", 0) for item in evidence)
            status = IntelligenceStatus.MAJOR_UPDATE.value if maximum >= 75 else IntelligenceStatus.UPDATE.value if maximum >= 45 else IntelligenceStatus.MINOR_UPDATE.value
        else:
            status = IntelligenceStatus.NO_MAJOR_UPDATE.value if healthy and searched else IntelligenceStatus.INSUFFICIENT_EVIDENCE.value
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
