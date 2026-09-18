"""Per-micro-topic evidence boundaries passed to retrieval and analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .identity import make_content_id, make_source_id


@dataclass(frozen=True)
class EvidenceAuthorizationPolicy:
    required_entities: tuple[str, ...] = ()
    optional_entities: tuple[str, ...] = ()
    forbidden_entities: tuple[str, ...] = ()
    required_events: tuple[str, ...] = ()
    optional_events: tuple[str, ...] = ()
    forbidden_events: tuple[str, ...] = ()


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
    authorization_policy: EvidenceAuthorizationPolicy = EvidenceAuthorizationPolicy()

    allow_historical: bool = True

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
        chunk_content_id = metadata.get("content_id")
        chunk_source_id = metadata.get("source_id")

        is_primary_current = (
            chunk_content_id == self.source_content_id
            and chunk_source_id == self.source_id
        )

        if not is_primary_current and not self.allow_historical:
            return False, "CONTENT_OR_SOURCE_MISMATCH"

        # Every chunk must match the micro-topic
        chunk_micro_matches = metadata.get("micro_topic_matches", [])
        target_id = self.micro_topic_id
        has_micro_match = any(
            isinstance(match, dict) and (
                match.get("micro_topic_id") == target_id
                or match.get("micro_topic") == target_id
                or (target_id.endswith(str(match.get("micro_topic_id", "___"))) if match.get("micro_topic_id") else False)
                or (str(match.get("micro_topic_id", "")).endswith(target_id) if target_id else False)
            )
            for match in chunk_micro_matches
        )
        if not has_micro_match:
            return False, "MISSING_CHUNK_MICRO_TOPIC_MATCH"

        event_ids = {str(value) for value in metadata.get("event_ids", []) if value}
        if metadata.get("event_id"):
            event_ids.add(str(metadata.get("event_id")))
        if self.allowed_events and not event_ids.intersection(self.allowed_events):
            return False, "EVENT_NOT_AUTHORIZED"

        event_id = str(metadata.get("event_id", ""))
        entity_ids = {str(value) for value in metadata.get("entity_ids", []) if value}
        policy = self.authorization_policy
        if event_id in policy.forbidden_events or entity_ids.intersection(policy.forbidden_entities):
            return False, "FORBIDDEN_EVENT_OR_ENTITY"
        if policy.required_events and event_id not in policy.required_events:
            return False, "REQUIRED_EVENT_MISSING"
        if policy.required_entities and not entity_ids.intersection(policy.required_entities):
            return False, "REQUIRED_ENTITY_MISSING"
        if self.allowed_entities and not entity_ids.intersection(self.allowed_entities):
            return False, "ENTITY_NOT_AUTHORIZED"

        if self.evidence_ids and metadata.get("evidence_id", "") not in self.evidence_ids:
            return False, "EVIDENCE_NOT_AUTHORIZED"
        if self.allowed_span_ids and metadata.get("span_id", "") not in self.allowed_span_ids:
            return False, "SPAN_NOT_AUTHORIZED"
        if self.allowed_claim_ids and metadata.get("claim_id", "") not in self.allowed_claim_ids:
            return False, "CLAIM_NOT_AUTHORIZED"
        if not metadata.get("provenance"):
            return False, "MISSING_PROVENANCE"

        # Determine explicit relationship
        if is_primary_current:
            relationship = "PRIMARY_CURRENT"
        elif self.allowed_events and event_ids.intersection(self.allowed_events):
            relationship = "SHARED_EVENT"
        elif self.allowed_entities and entity_ids.intersection(self.allowed_entities):
            relationship = "SHARED_ENTITY"
        else:
            relationship = "HISTORICAL_RELEVANT"

        metadata["authorization_reason"] = relationship
        metadata["micro_topic_id"] = self.micro_topic_id
        if "evidence_id" not in metadata:
            metadata["evidence_id"] = chunk.get("id", f"{chunk_content_id}:chunk")

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
            "authorization_policy": {
                "required_entities": list(self.authorization_policy.required_entities),
                "optional_entities": list(self.authorization_policy.optional_entities),
                "forbidden_entities": list(self.authorization_policy.forbidden_entities),
                "required_events": list(self.authorization_policy.required_events),
                "optional_events": list(self.authorization_policy.optional_events),
                "forbidden_events": list(self.authorization_policy.forbidden_events),
            },
            "evidence_isolated": True,
        }


class EvidenceScopeBuilder:
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
        # A document-level entity/event list is useful only when no finer
        # micro-topic annotation exists.  Once annotations exist, importing
        # unscoped document metadata would authorize cross-topic evidence.
        topic_matches = [
            match for match in metadata.get("micro_topic_matches", [])
            if isinstance(match, dict)
            and match.get("micro_topic_id") == classification.get("micro_topic_id", classification.get("micro_topic"))
        ]
        if topic_matches:
            entity_ids = tuple(sorted({str(value) for match in topic_matches for value in match.get("entity_ids", []) if value}))
            event_ids = tuple(sorted({str(value) for match in topic_matches for value in [*match.get("event_ids", []), match.get("event_id")] if value}))
            match_span_ids = tuple(sorted({str(value) for match in topic_matches for value in match.get("span_ids", []) if value}))
            match_claim_ids = tuple(sorted({str(value) for match in topic_matches for value in match.get("claim_ids", []) if value}))
            match_evidence_ids = tuple(sorted({str(value) for match in topic_matches for value in match.get("evidence_ids", []) if value}))
        else:
            entity_ids = tuple(str(value) for value in metadata.get("entity_ids", []) if value)
            event_ids = tuple(str(value) for value in [*metadata.get("event_ids", []), metadata.get("event_id", "")] if value)
            match_span_ids = ()
            match_claim_ids = ()
            match_evidence_ids = ()
        policy_data = classification.get("evidence_authorization", {}) or {}
        policy = EvidenceAuthorizationPolicy(
            required_entities=tuple(str(value) for value in policy_data.get("required_entities", [])),
            optional_entities=tuple(str(value) for value in policy_data.get("optional_entities", [])),
            forbidden_entities=tuple(str(value) for value in policy_data.get("forbidden_entities", [])),
            required_events=tuple(str(value) for value in policy_data.get("required_events", [])),
            optional_events=tuple(str(value) for value in policy_data.get("optional_events", [])),
            forbidden_events=tuple(str(value) for value in policy_data.get("forbidden_events", [])),
        )
        return EvidenceScope(
            micro_topic_id=str(classification.get("micro_topic_id", classification.get("micro_topic", ""))),
            source_content_id=content_id,
            source_id=source_id,
            allowed_span_ids=tuple(signal_span_ids) or match_span_ids,
            allowed_claim_ids=tuple(claim_ids) or match_claim_ids,
            allowed_entities=entity_ids,
            allowed_events=event_ids,
            evidence_ids=tuple(evidence_ids) or match_evidence_ids,
            isolation_confidence=float(classification.get("routing_confidence", classification.get("classification_confidence", classification.get("confidence", 0.0)))),
            authorization_policy=policy,
        )
