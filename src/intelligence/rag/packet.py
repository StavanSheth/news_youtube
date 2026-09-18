"""Structured context packet delivered to bounded AI analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContextPacket:
    run_id: str
    edition_key: str
    micro_topic_id: str
    theme_id: str
    query: str
    current_content: dict[str, Any] = field(default_factory=dict)
    retrieved_evidence: tuple[dict[str, Any], ...] = ()
    event_context: dict[str, Any] = field(default_factory=dict)
    entity_context: dict[str, Any] = field(default_factory=dict)
    source_context: dict[str, Any] = field(default_factory=dict)
    ranking: dict[str, Any] = field(default_factory=dict)
    diversity: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    budget: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    @property
    def evidence_ids(self) -> list[str]:
        result = []
        for chunk in self.retrieved_evidence:
            chunk_id = chunk.get("id") or chunk.get("metadata", {}).get("evidence_id")
            if chunk_id:
                result.append(str(chunk_id))
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "edition_key": self.edition_key,
            "micro_topic_id": self.micro_topic_id,
            "theme_id": self.theme_id,
            "query": self.query,
            "current_content": self.current_content,
            "retrieved_evidence": list(self.retrieved_evidence),
            "event_context": self.event_context,
            "entity_context": self.entity_context,
            "source_context": self.source_context,
            "ranking": self.ranking,
            "diversity": self.diversity,
            "provenance": self.provenance,
            "budget": self.budget,
            "warnings": list(self.warnings),
            "evidence_ids": self.evidence_ids,
        }
