"""Per-micro-topic evidence boundaries passed to retrieval and analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvidenceScope:
    micro_topic_id: str
    source_content_id: str
    source_id: str
    allowed_spans: tuple[str, ...] = ()
    allowed_claims: tuple[str, ...] = ()
    allowed_entities: tuple[str, ...] = ()
    allowed_events: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    isolation_reason: str = "matched_micro_topic_signals"
    isolation_confidence: float = 0.0

    def __post_init__(self) -> None:
        if not self.micro_topic_id or not self.source_content_id or not self.source_id:
            raise ValueError("EvidenceScope requires micro-topic, content, and source identities")
        if not 0 <= self.isolation_confidence <= 1:
            raise ValueError("EvidenceScope isolation confidence must be between 0 and 1")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("EvidenceScope evidence IDs must be unique")

    def allows(self, chunk: dict[str, Any]) -> bool:
        metadata = chunk.get("metadata", {})
        identity_ok = (
            metadata.get("micro_topic_id") == self.micro_topic_id
            and metadata.get("content_id") == self.source_content_id
            and metadata.get("source_id") == self.source_id
        )
        if not identity_ok:
            return False
        if self.allowed_events and metadata.get("event_id", "") not in self.allowed_events:
            return False
        if self.allowed_entities:
            chunk_entities = set(metadata.get("entity_ids", []))
            if not chunk_entities.intersection(self.allowed_entities):
                return False
        if self.evidence_ids and metadata.get("evidence_id", "") not in self.evidence_ids:
            return False
        return True

    def to_metadata(self) -> dict[str, Any]:
        return {
            "micro_topic_id": self.micro_topic_id,
            "source_content_id": self.source_content_id,
            "content_id": self.source_content_id,
            "source_id": self.source_id,
            "evidence_ids": list(self.evidence_ids),
            "allowed_entities": list(self.allowed_entities),
            "allowed_events": list(self.allowed_events),
            "isolation_reason": self.isolation_reason,
            "isolation_confidence": self.isolation_confidence,
            "evidence_isolated": True,
        }
