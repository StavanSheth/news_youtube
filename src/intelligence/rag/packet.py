"""Authoritative immutable ContextPacket for bounded AI analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContextPacket:
    """Immutable, provenance-preserving context packet delivered to AI analysis."""

    micro_topic_id: str
    query: str
    evidence: tuple[dict[str, Any], ...] = ()
    evidence_ids: tuple[str, ...] = ()
    content_ids: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    event_ids: tuple[str, ...] = ()
    entity_ids: tuple[str, ...] = ()
    retrieval_trace: dict[str, Any] = field(default_factory=dict)
    ranking_trace: dict[str, Any] = field(default_factory=dict)
    diversity_trace: dict[str, Any] = field(default_factory=dict)
    budget_trace: dict[str, Any] = field(default_factory=dict)
    # Extended and backwards-compatible attributes
    run_id: str = "local_run"
    edition_key: str = "default_edition"
    theme_id: str = ""
    current_content: dict[str, Any] = field(default_factory=dict)
    event_context: dict[str, Any] = field(default_factory=dict)
    entity_context: dict[str, Any] = field(default_factory=dict)
    source_context: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    retrieved_evidence: tuple[dict[str, Any], ...] | list[dict[str, Any]] = ()
    ranking: dict[str, Any] = field(default_factory=dict)
    diversity: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    budget: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        ev = self.evidence or self.retrieved_evidence or ()
        if not isinstance(ev, tuple):
            ev = tuple(ev)
        object.__setattr__(self, "evidence", ev)
        object.__setattr__(self, "retrieved_evidence", ev)

        if self.ranking and not self.ranking_trace:
            object.__setattr__(self, "ranking_trace", dict(self.ranking))
        elif self.ranking_trace and not self.ranking:
            object.__setattr__(self, "ranking", dict(self.ranking_trace))

        if self.diversity and not self.diversity_trace:
            object.__setattr__(self, "diversity_trace", dict(self.diversity))
        elif self.diversity_trace and not self.diversity:
            object.__setattr__(self, "diversity", dict(self.diversity_trace))

        if self.budget and not self.budget_trace:
            object.__setattr__(self, "budget_trace", dict(self.budget))
        elif self.budget_trace and not self.budget:
            object.__setattr__(self, "budget", dict(self.budget_trace))

        if not self.evidence_ids and ev:
            ev_ids = []
            c_ids = set()
            s_ids = set()
            for chunk in ev:
                cid = chunk.get("id") or chunk.get("metadata", {}).get("evidence_id")
                if cid and str(cid) not in ev_ids:
                    ev_ids.append(str(cid))
                content_id = chunk.get("metadata", {}).get("content_id")
                if content_id:
                    c_ids.add(str(content_id))
                source_id = chunk.get("metadata", {}).get("source_id") or chunk.get("metadata", {}).get("source")
                if source_id:
                    s_ids.add(str(source_id))
            object.__setattr__(self, "evidence_ids", tuple(ev_ids))
            if not self.content_ids:
                object.__setattr__(self, "content_ids", tuple(sorted(c_ids)))
            if not self.source_ids:
                object.__setattr__(self, "source_ids", tuple(sorted(s_ids)))

    @classmethod
    def create(
        cls,
        micro_topic_id: str,
        query: str,
        evidence: list[dict[str, Any]] | tuple[dict[str, Any], ...],
        *,
        run_id: str = "local_run",
        edition_key: str = "default_edition",
        theme_id: str = "",
        current_content: dict[str, Any] | None = None,
        retrieval_trace: dict[str, Any] | None = None,
        ranking_trace: dict[str, Any] | None = None,
        diversity_trace: dict[str, Any] | None = None,
        budget_trace: dict[str, Any] | None = None,
        event_ids: list[str] | None = None,
        entity_ids: list[str] | None = None,
    ) -> "ContextPacket":
        evidence_tuple = tuple(evidence)
        ev_ids = []
        content_ids = set()
        source_ids = set()
        ev_ids_set = set()

        for chunk in evidence_tuple:
            cid = chunk.get("id") or chunk.get("metadata", {}).get("evidence_id")
            if cid and str(cid) not in ev_ids_set:
                ev_ids.append(str(cid))
                ev_ids_set.add(str(cid))
            content_id = chunk.get("metadata", {}).get("content_id")
            if content_id:
                content_ids.add(str(content_id))
            source_id = chunk.get("metadata", {}).get("source_id") or chunk.get("metadata", {}).get("source")
            if source_id:
                source_ids.add(str(source_id))

        return cls(
            micro_topic_id=micro_topic_id,
            query=query,
            evidence=evidence_tuple,
            evidence_ids=tuple(ev_ids),
            content_ids=tuple(sorted(content_ids)),
            source_ids=tuple(sorted(source_ids)),
            event_ids=tuple(event_ids or []),
            entity_ids=tuple(entity_ids or []),
            retrieval_trace=retrieval_trace or {},
            ranking_trace=ranking_trace or {},
            diversity_trace=diversity_trace or {},
            budget_trace=budget_trace or {},
            run_id=run_id,
            edition_key=edition_key,
            theme_id=theme_id,
            current_content=current_content or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "micro_topic_id": self.micro_topic_id,
            "query": self.query,
            "evidence": list(self.evidence),
            "retrieved_evidence": list(self.evidence),
            "evidence_ids": list(self.evidence_ids),
            "content_ids": list(self.content_ids),
            "source_ids": list(self.source_ids),
            "event_ids": list(self.event_ids),
            "entity_ids": list(self.entity_ids),
            "retrieval_trace": self.retrieval_trace,
            "ranking_trace": self.ranking_trace,
            "diversity_trace": self.diversity_trace,
            "budget_trace": self.budget_trace,
            "ranking": self.ranking or self.ranking_trace,
            "diversity": self.diversity or self.diversity_trace,
            "provenance": self.provenance or {
                "evidence_count": len(self.evidence),
                "evidence_ids": list(self.evidence_ids),
            },
            "budget": self.budget or self.budget_trace,
            "run_id": self.run_id,
            "edition_key": self.edition_key,
            "theme_id": self.theme_id,
            "current_content": self.current_content,
            "event_context": self.event_context,
            "entity_context": self.entity_context,
            "source_context": self.source_context,
            "warnings": list(self.warnings),
        }
