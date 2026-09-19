"""Authoritative retrieval request builder for RAG."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RetrievalRequest:
    query: str
    micro_topic_id: str
    theme_id: str
    domain: str = ""
    topic: str = ""
    required_concepts: tuple[str, ...] = ()
    preferred_sources: tuple[str, ...] = ()
    preferred_source_types: tuple[str, ...] = ()
    evidence_types: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    freshness: str = "30d"
    event_context: dict[str, Any] = field(default_factory=dict)
    entity_context: dict[str, Any] = field(default_factory=dict)
    max_results: int = 4
    max_context: int = 12000
    publication_cutoff: str | None = None
    retrieval_intent: dict[str, Any] = field(default_factory=dict)
    exclusion_concepts: tuple[str, ...] | list[str] = ()

    def __post_init__(self) -> None:
        merged = []
        for item in (self.exclusions, self.exclusion_concepts):
            if isinstance(item, (list, tuple, set)):
                merged.extend(str(x) for x in item if x)
            elif item:
                merged.append(str(item))
        distinct = tuple(dict.fromkeys(merged))
        object.__setattr__(self, "exclusions", distinct)
        object.__setattr__(self, "exclusion_concepts", distinct)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "micro_topic_id": self.micro_topic_id,
            "theme_id": self.theme_id,
            "domain": self.domain,
            "topic": self.topic,
            "required_concepts": list(self.required_concepts),
            "preferred_sources": list(self.preferred_sources),
            "preferred_source_types": list(self.preferred_source_types),
            "evidence_types": list(self.evidence_types),
            "exclusions": list(self.exclusions),
            "exclusion_concepts": list(self.exclusion_concepts),
            "freshness": self.freshness,
            "event_context": self.event_context,
            "entity_context": self.entity_context,
            "max_results": self.max_results,
            "max_context": self.max_context,
            "publication_cutoff": self.publication_cutoff,
            "retrieval_intent": self.retrieval_intent,
        }


def build_retrieval_request(
    micro_topic: str | dict[str, Any],
    theme: dict[str, Any],
    classification: dict[str, Any] | None = None,
    event_context: dict[str, Any] | None = None,
    cutoff: datetime | str | None = None,
    budget: dict[str, Any] | None = None,
) -> RetrievalRequest:
    """Build a complete, normalized RetrievalRequest contract."""
    classification = classification or {}
    event_context = event_context or {}
    budget = budget or {}

    micro_topic_id = (
        micro_topic if isinstance(micro_topic, str)
        else micro_topic.get("micro_topic_id") or micro_topic.get("micro_topic") or classification.get("micro_topic", "")
    )
    theme_id = str(theme.get("theme_id", theme.get("id", "")))
    domain = str(classification.get("domain", theme.get("domain", "")))
    topic = str(classification.get("topic", theme.get("topic", "")))

    # Retrieval intent resolution
    raw_theme_intent = theme.get("retrieval_intent", {}) or {}
    theme_intent = {"primary_query": raw_theme_intent} if isinstance(raw_theme_intent, str) else dict(raw_theme_intent)
    raw_profile_intent = (
        classification.get("profile", {}).get("retrieval_intent", {})
        if isinstance(classification.get("profile"), dict)
        else {}
    ) or {}
    profile_intent = {"primary_query": raw_profile_intent} if isinstance(raw_profile_intent, str) else dict(raw_profile_intent)
    intent = {**theme_intent, **profile_intent}

    required_concepts = tuple(
        str(c) for c in (intent.get("required_concepts") or [micro_topic_id]) if c
    )
    preferred_sources = tuple(str(s) for s in (intent.get("preferred_sources") or []) if s)
    preferred_source_types = tuple(str(st) for st in (intent.get("preferred_source_types") or []) if st)
    evidence_types = tuple(str(et) for et in (intent.get("evidence_types") or []) if et)
    exclusions = tuple(str(ex) for ex in (intent.get("exclusion_concepts") or intent.get("exclusions") or []) if ex)
    freshness = str(intent.get("freshness", "30d"))

    # Entity context
    entity_context = {}
    if "entities" in event_context:
        entity_context["entities"] = event_context["entities"]

    # Assembled deterministic query string
    query_parts = [
        domain,
        topic,
        micro_topic_id,
        " ".join(classification.get("signals", [])),
        " ".join(required_concepts),
        " ".join(preferred_source_types),
        " ".join(event_context.get("entities", [])),
    ]
    query = " ".join(filter(None, (p.strip() for p in query_parts)))

    max_results = int(budget.get("max_rag_items", budget.get("retrieval_top_k", 4)))
    max_context = int(budget.get("max_context_chars", 12000))

    cutoff_str = cutoff.isoformat() if isinstance(cutoff, datetime) else (str(cutoff) if cutoff else None)

    return RetrievalRequest(
        query=query,
        micro_topic_id=micro_topic_id,
        theme_id=theme_id,
        domain=domain,
        topic=topic,
        required_concepts=required_concepts,
        preferred_sources=preferred_sources,
        preferred_source_types=preferred_source_types,
        evidence_types=evidence_types,
        exclusions=exclusions,
        freshness=freshness,
        event_context=event_context,
        entity_context=entity_context,
        max_results=max_results,
        max_context=max_context,
        publication_cutoff=cutoff_str,
        retrieval_intent={
            "required_concepts": list(required_concepts),
            "preferred_sources": list(preferred_sources),
            "preferred_source_types": list(preferred_source_types),
            "evidence_types": list(evidence_types),
            "exclusion_concepts": list(exclusions),
            "freshness": freshness,
        },
    )
