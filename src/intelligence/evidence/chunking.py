"""Authoritative chunking interfaces and deterministic window chunker."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from ..contracts import EvidenceType, provenance_from_mapping
from ..identity import make_content_id, make_source_id
from ..microtopics import score_micro_topic_chunk


@dataclass(frozen=True)
class Chunk:
    """Immutable representation of a text chunk with complete provenance and span identity."""

    chunk_id: str
    text: str
    content_id: str
    source_id: str
    span_start: int
    span_end: int
    span_id: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to repository-standard chunk dictionary format."""
        meta = dict(self.metadata)
        if self.span_id and "span_id" not in meta:
            meta["span_id"] = self.span_id
        if self.content_id and "content_id" not in meta:
            meta["content_id"] = self.content_id
        if self.source_id and "source_id" not in meta:
            meta["source_id"] = self.source_id
        if "span_start" not in meta:
            meta["span_start"] = self.span_start
        if "span_end" not in meta:
            meta["span_end"] = self.span_end
        return {
            "id": self.chunk_id,
            "text": self.text,
            "metadata": meta,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Chunk":
        metadata = dict(data.get("metadata", {}))
        chunk_id = str(data.get("id", ""))
        text = str(data.get("text", ""))
        content_id = str(metadata.get("content_id", ""))
        source_id = str(metadata.get("source_id", ""))
        span_id = str(metadata.get("span_id", ""))
        span_start = int(metadata.get("span_start", 0))
        span_end = int(metadata.get("span_end", len(text)))
        return cls(
            chunk_id=chunk_id,
            text=text,
            content_id=content_id,
            source_id=source_id,
            span_start=span_start,
            span_end=span_end,
            span_id=span_id,
            metadata=metadata,
        )


class ChunkingStrategy(Protocol):
    """Protocol for chunking strategies."""

    def chunk_item(self, item: dict[str, Any]) -> list[Chunk]:
        """Split item into chunks with span and provenance metadata."""
        ...


@dataclass(frozen=True)
class CharacterChunker:
    """Deterministic character-window chunking strategy with fixed overlap."""

    size: int = 1400
    overlap: int = 180

    def chunk_item(self, item: dict[str, Any]) -> list[Chunk]:
        """Split an item into deterministic chunks preserving complete metadata."""
        text = item.get("text", "") or ""
        stride = max(1, self.size - self.overlap)
        windows = [
            (index, min(len(text), index + self.size), text[index : index + self.size])
            for index in range(0, max(1, len(text)), stride)
        ] or [(0, 0, "")]

        source_id = item.get("metadata", {}).get("source_id") or make_source_id(item.get("source", "unknown"))
        content_id = item.get("metadata", {}).get("content_id") or make_content_id(
            source_id, item.get("url", ""), item.get("title", ""), item.get("published_at", ""), text
        )
        evidence_type = "transcript" if item.get("kind") == "youtube" else "article"
        retrieved_at = item.get("metadata", {}).get("retrieved_at") or datetime.now(UTC).isoformat()
        provenance_type = EvidenceType.TRANSCRIPT if item.get("kind") == "youtube" else EvidenceType.ARTICLE

        classifications: list[dict[str, Any]] = []
        if item.get("metadata", {}).get("classification"):
            classifications.append(item["metadata"]["classification"])
        if isinstance(item.get("metadata", {}).get("classifications"), list):
            for c in item["metadata"]["classifications"]:
                if isinstance(c, dict) and c not in classifications:
                    classifications.append(c)
        if isinstance(item.get("micro_topics"), list):
            for mt in item["micro_topics"]:
                if isinstance(mt, dict) and mt not in classifications:
                    classifications.append(mt)

        result: list[Chunk] = []
        for index, (start, end, chunk_text) in enumerate(windows):
            provenance = None
            if item.get("url", "").startswith(("http://", "https://")):
                provenance = provenance_from_mapping(
                    {
                        **item,
                        "metadata": {
                            **item.get("metadata", {}),
                            "content_id": content_id,
                            "source_id": source_id,
                            "retrieved_at": retrieved_at,
                        },
                    },
                    provenance_type,
                    chunk_text,
                ).to_dict()

            micro_topic_matches: list[dict[str, Any]] = []
            last_match: dict[str, Any] = {}
            for cls_info in classifications:
                match = score_micro_topic_chunk(chunk_text, cls_info)
                last_match = match
                if match.get("relevant"):
                    micro_topic_id = str(cls_info.get("micro_topic_id") or cls_info.get("micro_topic", ""))
                    micro_topic_slug = str(cls_info.get("micro_topic", ""))
                    match_entry = {
                        "micro_topic_id": micro_topic_id,
                        "micro_topic": micro_topic_slug,
                        "score": match["score"],
                        "matched_signals": match["matched_signals"],
                        "matched_groups": match.get("matched_signal_groups", {}),
                        "confidence": match["score"],
                    }
                    micro_topic_matches.append(match_entry)
                    if micro_topic_slug and micro_topic_slug != micro_topic_id:
                        micro_topic_matches.append({
                            **match_entry,
                            "micro_topic_id": micro_topic_slug,
                        })

            span_id = f"{content_id}:span:{start}:{end}"
            chunk_id = f"{content_id}:{index}"

            chunk_meta = {
                key: item.get(key, "")
                for key in ("id", "url", "source", "title", "kind", "published_at")
            } | {
                "source_id": source_id,
                "content_id": content_id,
                "provenance": provenance,
                "provenance_status": "VALID" if provenance else "MISSING_SOURCE_URL",
                "evidence_type": evidence_type,
                "event_id": item.get("metadata", {}).get("event_id", ""),
                "topics": item.get("topics", []),
                "micro_topics": item.get("micro_topics", []),
                "updated_at": item.get("metadata", {}).get("updated_at", ""),
                "retrieved_at": retrieved_at,
                "trust_tier": item.get("metadata", {}).get("trust_tier", 4),
                "micro_topic_id": item.get("metadata", {}).get("micro_topic_id", ""),
                "micro_topic_matches": micro_topic_matches,
                "span_id": span_id,
                "span_start": start,
                "span_end": end,
                "micro_topic_match": last_match,
                "evidence_span_ids": [],
            }

            result.append(
                Chunk(
                    chunk_id=chunk_id,
                    text=chunk_text,
                    content_id=content_id,
                    source_id=source_id,
                    span_start=start,
                    span_end=end,
                    span_id=span_id,
                    metadata=chunk_meta,
                )
            )

        return result


def deterministic_chunks(
    item: dict[str, Any], size: int = 1400, overlap: int = 180
) -> list[dict[str, Any]]:
    """Authoritative character-window chunking producing standard dict format."""
    chunker = CharacterChunker(size=size, overlap=overlap)
    return [chunk.to_dict() for chunk in chunker.chunk_item(item)]


def semantic_chunks(
    item: dict[str, Any], size: int = 1400, overlap: int = 180
) -> list[dict[str, Any]]:
    """Backward-compatible alias for deterministic character-window chunking."""
    return deterministic_chunks(item, size, overlap)
