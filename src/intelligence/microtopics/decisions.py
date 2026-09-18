"""Micro-topic decision and evaluation context contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class MicroTopicDecision:
    """Authoritative typed decision contract for one micro-topic routing decision."""

    micro_topic_id: str
    domain_id: str
    topic_id: str
    confidence: float | None = None
    classification_score: float | None = None
    runner_up_score: float = 0.0
    margin: float = 0.0
    matched_signals: tuple[str, ...] = ()
    negative_matches: tuple[str, ...] = ()
    classification_status: str = "PRIMARY"  # PRIMARY, SECONDARY, REJECTED, CONTRADICTORY
    significance: float = 0.0
    event_ids: tuple[str, ...] = ()
    entity_ids: tuple[str, ...] = ()
    evidence_scope_id: str = ""
    # Compatibility and extended audit attributes
    threshold: float | None = None
    matched_signal_groups: dict[str, Any] = field(default_factory=dict)
    missing_signal_groups: tuple[str, ...] = ()
    distractors: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    theme_id: str | None = None
    theme_resolution: str | dict[str, Any] | None = None
    profile_origin: str | None = None
    decision: str | None = None
    score: float | None = None

    def __post_init__(self) -> None:
        if self.decision is not None and self.classification_status == "PRIMARY":
            object.__setattr__(self, "classification_status", self.decision)
        elif self.classification_status and self.decision is None:
            object.__setattr__(self, "decision", self.classification_status)
        if self.score is not None and self.classification_score is None:
            object.__setattr__(self, "classification_score", self.score)
        elif self.classification_score is not None and self.score is None:
            object.__setattr__(self, "score", self.classification_score)

    @property
    def positive_signals(self) -> tuple[str, ...]:
        return self.matched_signals

    @property
    def negative_signals(self) -> tuple[str, ...]:
        return self.negative_matches

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MicroTopicDecision":
        def opt_number(name: str) -> float | None:
            raw = value.get(name)
            if raw is None:
                return None
            if isinstance(raw, bool):
                raise ValueError(f"Invalid decision {name}: boolean")
            try:
                return float(raw)
            except (TypeError, ValueError) as error:
                raise ValueError(f"Invalid decision {name}: {raw!r}") from error

        def number(name: str, default: float = 0.0) -> float:
            v = opt_number(name)
            return v if v is not None else default

        # Map score / classification_score
        score_val = opt_number("classification_score")
        if score_val is None:
            score_val = opt_number("score")

        # Map decision / classification_status
        status_val = str(value.get("classification_status") or value.get("decision") or "UNRESOLVED")
        # Map negative_matches / negative_signals
        neg_matches = tuple(value.get("negative_matches") or value.get("negative_signals") or ())
        # Map positive_signals / matched_signals
        pos_signals = tuple(value.get("matched_signals") or value.get("positive_signals") or ())

        return cls(
            micro_topic_id=str(value.get("micro_topic_id", "")),
            domain_id=str(value.get("domain_id", "")),
            topic_id=str(value.get("topic_id", "")),
            confidence=opt_number("confidence"),
            classification_score=score_val,
            runner_up_score=number("runner_up_score", 0.0),
            margin=number("margin", 0.0),
            matched_signals=pos_signals,
            negative_matches=neg_matches,
            classification_status=status_val,
            significance=number("significance", 0.0),
            event_ids=tuple(str(e) for e in value.get("event_ids", ())),
            entity_ids=tuple(str(e) for e in value.get("entity_ids", ())),
            evidence_scope_id=str(value.get("evidence_scope_id", "")),
            threshold=opt_number("threshold"),
            matched_signal_groups=dict(value.get("matched_signal_groups") or {}),
            missing_signal_groups=tuple(value.get("missing_signal_groups") or ()),
            distractors=tuple(value.get("distractors") or ()),
            contradictions=tuple(value.get("contradictions") or ()),
            exclusions=tuple(value.get("exclusions") or ()),
            theme_id=value.get("theme_id"),
            theme_resolution=value.get("theme_resolution"),
            profile_origin=value.get("profile_origin"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "micro_topic_id": self.micro_topic_id,
            "domain_id": self.domain_id,
            "topic_id": self.topic_id,
            "confidence": self.confidence,
            "classification_score": self.classification_score,
            "runner_up_score": self.runner_up_score,
            "margin": self.margin,
            "matched_signals": list(self.matched_signals),
            "negative_matches": list(self.negative_matches),
            "classification_status": self.classification_status,
            "significance": self.significance,
            "event_ids": list(self.event_ids),
            "entity_ids": list(self.entity_ids),
            "evidence_scope_id": self.evidence_scope_id,
            # Backwards-compatible aliases
            "decision": self.classification_status,
            "score": self.classification_score,
            "threshold": self.threshold,
            "matched_signal_groups": self.matched_signal_groups,
            "missing_signal_groups": list(self.missing_signal_groups),
            "positive_signals": list(self.matched_signals),
            "negative_signals": list(self.negative_matches),
            "distractors": list(self.distractors),
            "contradictions": list(self.contradictions),
            "exclusions": list(self.exclusions),
            "theme_id": self.theme_id,
            "theme_resolution": self.theme_resolution,
            "profile_origin": self.profile_origin,
        }


@dataclass(frozen=True)
class MicroTopicEvaluationContext:
    """Separate immutable evaluation context for one evaluated micro-topic."""

    micro_topic_id: str
    classification_decision: MicroTopicDecision
    theme: dict[str, Any]
    retrieval_intent: dict[str, Any]
    evidence_scope: dict[str, Any]
    budget_scope: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "micro_topic_id": self.micro_topic_id,
            "classification_decision": self.classification_decision.to_dict(),
            "theme": dict(self.theme),
            "retrieval_intent": dict(self.retrieval_intent),
            "evidence_scope": dict(self.evidence_scope),
            "budget_scope": dict(self.budget_scope),
        }
