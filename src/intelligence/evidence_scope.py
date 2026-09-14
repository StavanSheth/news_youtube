"""Per-micro-topic evidence boundaries passed to retrieval and analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .identity import make_content_id, make_source_id


@dataclass(frozen=True)
class EvidenceScope:
    micro_topic_id: str
    source_content_id: str
    source_id: str
    allowed_span_ids: tuple[str, ...] = ()
    allowed_claim_ids: tuple[str, ...] = ()
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
        return self.authorize(chunk)[0]

    def authorize(self, chunk: dict[str, Any]) -> tuple[bool, str]:
        metadata = chunk.get("metadata", {})
        identity_ok = (
            metadata.get("content_id") == self.source_content_id
            and metadata.get("source_id") == self.source_id
        )
        if not identity_ok:
            return False, "CONTENT_OR_SOURCE_MISMATCH"
        if not any(match.get("micro_topic_id") == self.micro_topic_id for match in metadata.get("micro_topic_matches", []) if isinstance(match, dict)):
            return False, "MISSING_CHUNK_MICRO_TOPIC_MATCH"
        if self.allowed_events and metadata.get("event_id", "") not in self.allowed_events:
            return False, "EVENT_NOT_AUTHORIZED"
        if self.allowed_entities:
            chunk_entities = set(metadata.get("entity_ids", []))
            if not chunk_entities.intersection(self.allowed_entities):
                return False, "ENTITY_NOT_AUTHORIZED"
        if self.evidence_ids and metadata.get("evidence_id", "") not in self.evidence_ids:
            return False, "EVIDENCE_NOT_AUTHORIZED"
        if self.allowed_span_ids and metadata.get("span_id", "") not in self.allowed_span_ids:
            return False, "SPAN_NOT_AUTHORIZED"
        if self.allowed_claim_ids and metadata.get("claim_id", "") not in self.allowed_claim_ids:
            return False, "CLAIM_NOT_AUTHORIZED"
        if not metadata.get("provenance"):
            return False, "MISSING_PROVENANCE"
        return True, "AUTHORIZED"

    def to_metadata(self) -> dict[str, Any]:
        return {
            "micro_topic_id": self.micro_topic_id,
            "source_content_id": self.source_content_id,
            "content_id": self.source_content_id,
            "source_id": self.source_id,
            "evidence_ids": list(self.evidence_ids),
            "allowed_span_ids": list(self.allowed_span_ids),
            "allowed_claim_ids": list(self.allowed_claim_ids),
            "allowed_entities": list(self.allowed_entities),
            "allowed_events": list(self.allowed_events),
            "isolation_reason": self.isolation_reason,
            "isolation_confidence": self.isolation_confidence,
            "evidence_isolated": True,
        }


class EvidenceScopeBuilder:
    """Build scopes from available provenance without inventing identifiers."""

    @staticmethod
    def build(
        item: dict[str, Any],
        classification: dict[str, Any],
        *,
        signal_span_ids: tuple[str, ...] = (),
        claim_ids: tuple[str, ...] = (),
        evidence_ids: tuple[str, ...] = (),
    ) -> EvidenceScope:
        metadata = item.get("metadata", {})
        source_id = str(metadata.get("source_id", "")).strip() or make_source_id(str(item.get("source", "")).strip())
        content_id = str(metadata.get("content_id", "")).strip() or make_content_id(source_id, item.get("url", ""), item.get("title", ""), item.get("published_at", ""), item.get("text", ""))
        entity_ids = tuple(str(value) for value in metadata.get("entity_ids", []) if value)
        event_ids = tuple(str(value) for value in [metadata.get("event_id", "")] if value)
        return EvidenceScope(
            micro_topic_id=str(classification.get("micro_topic_id", classification.get("micro_topic", ""))),
            source_content_id=content_id,
            source_id=source_id,
            allowed_span_ids=tuple(signal_span_ids),
            allowed_claim_ids=tuple(claim_ids),
            allowed_entities=entity_ids,
            allowed_events=event_ids,
            evidence_ids=tuple(evidence_ids),
            isolation_confidence=float(classification.get("routing_confidence", classification.get("classification_confidence", classification.get("confidence", 0.0)))),
        )
