"""Signal models, extraction, and group policy evaluation for micro-topics."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

GENERIC_TERMS = {
    "ai", "model", "models", "technology", "research", "policy", "security", "systems",
    "application", "applications", "engineering", "infrastructure", "development", "commercial",
    "government", "program", "programs", "market", "markets", "strategy", "funding", "supply",
    "chains", "tools", "tooling", "platform", "platforms", "open", "source", "digital", "cloud",
}


def words(value: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]{2,}", value.lower()) if word not in {"and", "the", "for", "with"}}


def phrase_found(phrase: str, text: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(phrase.lower())}(?!\w)", text.lower()))


def parse_signal(value: Any, *, default_strength: str = "medium", default_type: str = "distractor") -> dict[str, str]:
    if isinstance(value, dict):
        strength = str(value.get("strength", default_strength)).lower()
        phrase = str(value.get("phrase", "")).strip()
        return {
            "phrase": phrase,
            "signal_id": f"signal-{re.sub(r'[^a-z0-9]+', '-', phrase.lower()).strip('-')}",
            "strength": strength,
            "type": str(value.get("type", "contradiction" if strength == "strong" else default_type)).lower(),
            "specificity": str(value.get("specificity", "specific" if len(str(value.get("phrase", "")).split()) >= 2 else "broad")),
            "source": str(value.get("source", "profile")),
        }
    phrase = str(value).strip()
    return {
        "phrase": phrase,
        "signal_id": f"signal-{re.sub(r'[^a-z0-9]+', '-', phrase.lower()).strip('-')}",
        "strength": default_strength,
        "type": default_type,
        "specificity": "specific" if len(phrase.split()) >= 2 else "broad",
        "source": "profile",
    }


def group_policy_satisfied(policy: Any, matched_groups: dict[str, Any]) -> tuple[bool, list[str]]:
    """Evaluate ALL, ANY, or AT_LEAST_N routing policy without implicit defaults."""
    if isinstance(policy, dict):
        mode = str(policy.get("mode", "AT_LEAST_N")).upper()
        groups = [str(value) for value in policy.get("groups", [])]
        minimum = int(policy.get("minimum", 1))
    else:
        mode, groups, minimum = "AT_LEAST_N", [str(value) for value in (policy or [])], 1
    matched = {group for group in groups if matched_groups.get(group)}
    missing = [group for group in groups if group not in matched]
    if not groups:
        return True, missing
    if mode == "ALL":
        return len(missing) == 0, missing
    if mode == "ANY":
        return bool(matched), missing
    if mode == "AT_LEAST_N":
        return len(matched) >= max(1, minimum), missing
    raise ValueError(f"Unknown signal group policy: {mode}")


@dataclass(frozen=True)
class MicroTopicSignalModel:
    """Rich declarative signal model for a single micro-topic."""

    micro_topic_id: str
    positive_signals: tuple[dict[str, str], ...] = ()
    negative_signals: tuple[dict[str, str], ...] = ()
    signal_groups: dict[str, Any] = field(default_factory=dict)
    aliases: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()
    required_concepts: tuple[str, ...] = ()
    exclusion_concepts: tuple[str, ...] = ()
    minimum_score: float = 0.5
    minimum_margin: float = 0.05
    significance_threshold: float = 0.6
    retrieval_intent: dict[str, Any] = field(default_factory=dict)
