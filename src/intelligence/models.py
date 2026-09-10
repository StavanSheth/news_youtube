from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from .contracts import EvidenceType, Provenance, SourceTimestamps, source_timestamps_from_mapping
from .identity import make_content_id, make_evidence_id, make_source_id


@dataclass
class SourceItem:
    id: str
    kind: str
    title: str
    url: str
    text: str
    published_at: str = ""
    source: str = ""
    priority: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamps: SourceTimestamps | None = None
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        self.timestamps = self.timestamps or source_timestamps_from_mapping(
            {"published_at": self.published_at, "metadata": self.metadata}, datetime.now(UTC)
        )
        self.published_at = self.timestamps.published_at.isoformat() if self.timestamps.published_at else self.published_at
        self.metadata.setdefault("timestamp_status", self.timestamps.publication_status.value)
        source_key = self.metadata.get("source_key") or self.metadata.get("source_id") or self.source or "unknown"
        self.metadata["source_key"] = source_key
        source_id = make_source_id(source_key)
        self.metadata["source_id"] = source_id
        if self.provenance is None and self.url.startswith(("http://", "https://")):
            content_id = self.metadata.setdefault(
                "content_id", make_content_id(source_id, self.url, self.title, self.published_at, self.text)
            )
            evidence_type = EvidenceType.TRANSCRIPT if self.kind == "youtube" else EvidenceType.ARTICLE
            self.provenance = Provenance(
                make_evidence_id(content_id, evidence_type.value, self.text[:360], self.url),
                content_id,
                source_id,
                self.url,
                evidence_type,
                int(self.metadata.get("trust_tier", 4) or 4),
                self.timestamps.retrieved_at or datetime.now(UTC),
            )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["timestamps"] = self.timestamps.to_dict() if self.timestamps else None
        payload["provenance"] = self.provenance.to_dict() if self.provenance else None
        return payload


@dataclass
class Analysis:
    item: SourceItem
    topics: list[str]
    score: float
    facts: list[str]
    interpretation: list[str]
    actionable_insights: list[str]
    routine: dict[str, list[str]] | None = None
    uncertainties: list[str] = field(default_factory=list)
    processed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["item"] = self.item.to_dict()
        return payload
