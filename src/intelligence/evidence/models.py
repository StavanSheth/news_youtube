"""Immutable Evidence model representing validated, provenance-preserving evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .chunking import Chunk


@dataclass(frozen=True)
class Evidence:
    """Immutable evidence unit with full provenance, source, and micro-topic identity."""

    evidence_id: str
    content_id: str
    source_id: str
    event_id: str = ""
    micro_topic_id: str = ""
    chunk_id: str = ""
    span_id: str = ""
    trust_tier: int = 4
    published_at: str = ""
    retrieved_at: str = ""
    url: str = ""
    title: str = ""
    text: str = ""
    evidence_type: str = "article"
    provenance: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raise ValueError("Evidence requires a non-empty evidence_id")
        if not self.content_id or not self.source_id:
            raise ValueError("Evidence requires content_id and source_id")
        if not 1 <= int(self.trust_tier) <= 4:
            raise ValueError("Evidence trust_tier must be between 1 and 4")

    def to_dict(self) -> dict[str, Any]:
        """Convert to standard dictionary format."""
        return {
            "evidence_id": self.evidence_id,
            "content_id": self.content_id,
            "source_id": self.source_id,
            "event_id": self.event_id,
            "micro_topic_id": self.micro_topic_id,
            "chunk_id": self.chunk_id,
            "span_id": self.span_id,
            "trust_tier": self.trust_tier,
            "published_at": self.published_at,
            "retrieved_at": self.retrieved_at,
            "url": self.url,
            "title": self.title,
            "text": self.text,
            "evidence_type": self.evidence_type,
            "provenance": dict(self.provenance),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_chunk(cls, chunk: Chunk | dict[str, Any], micro_topic_id: str = "") -> "Evidence":
        """Build an Evidence object from a Chunk instance or chunk dictionary."""
        if isinstance(chunk, Chunk):
            chunk_data = chunk.to_dict()
        else:
            chunk_data = chunk

        metadata = dict(chunk_data.get("metadata", {}))
        text = str(chunk_data.get("text", ""))
        chunk_id = str(chunk_data.get("id", ""))
        content_id = str(metadata.get("content_id", ""))
        source_id = str(metadata.get("source_id", ""))
        span_id = str(metadata.get("span_id", ""))
        event_id = str(metadata.get("event_id", ""))
        m_id = micro_topic_id or str(metadata.get("micro_topic_id", ""))
        trust_tier = int(metadata.get("trust_tier", 4) or 4)
        published_at = str(metadata.get("published_at", ""))
        retrieved_at = str(metadata.get("retrieved_at", "")) or datetime.now(UTC).isoformat()
        url = str(metadata.get("url", ""))
        title = str(metadata.get("title", ""))
        evidence_type = str(metadata.get("evidence_type", "article"))
        provenance = dict(metadata.get("provenance", {}) or {})
        evidence_id = str(metadata.get("evidence_id") or chunk_id or f"{content_id}:{span_id}")

        return cls(
            evidence_id=evidence_id,
            content_id=content_id,
            source_id=source_id,
            event_id=event_id,
            micro_topic_id=m_id,
            chunk_id=chunk_id,
            span_id=span_id,
            trust_tier=trust_tier,
            published_at=published_at,
            retrieved_at=retrieved_at,
            url=url,
            title=title,
            text=text,
            evidence_type=evidence_type,
            provenance=provenance,
            metadata=metadata,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Evidence":
        """Construct Evidence from serialized dictionary."""
        return cls(
            evidence_id=str(data.get("evidence_id", "")),
            content_id=str(data.get("content_id", "")),
            source_id=str(data.get("source_id", "")),
            event_id=str(data.get("event_id", "")),
            micro_topic_id=str(data.get("micro_topic_id", "")),
            chunk_id=str(data.get("chunk_id", "")),
            span_id=str(data.get("span_id", "")),
            trust_tier=int(data.get("trust_tier", 4) or 4),
            published_at=str(data.get("published_at", "")),
            retrieved_at=str(data.get("retrieved_at", "")),
            url=str(data.get("url", "")),
            title=str(data.get("title", "")),
            text=str(data.get("text", "")),
            evidence_type=str(data.get("evidence_type", "article")),
            provenance=dict(data.get("provenance", {}) or {}),
            metadata=dict(data.get("metadata", {}) or {}),
        )
