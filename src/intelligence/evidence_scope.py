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

    def to_metadata(self) -> dict[str, Any]:
        return {
            "micro_topic_id": self.micro_topic_id,
            "source_content_id": self.source_content_id,
            "source_id": self.source_id,
            "evidence_ids": list(self.evidence_ids),
            "allowed_entities": list(self.allowed_entities),
            "allowed_events": list(self.allowed_events),
            "isolation_reason": self.isolation_reason,
            "isolation_confidence": self.isolation_confidence,
            "evidence_isolated": True,
        }
