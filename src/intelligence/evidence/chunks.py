"""Authoritative Chunker interface providing deterministic and semantic chunking."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from ..ai.usage import estimate_tokens
from ..contracts import EvidenceType, provenance_from_mapping
from ..identity import make_content_id, make_source_id


class Chunker:
    """Unified chunker providing deterministic and semantic-compatible chunking."""

    @classmethod
    def deterministic(
        cls,
        item: dict[str, Any],
        chunk_size: int = 1400,
        chunk_overlap: int = 180,
    ) -> list[dict[str, Any]]:
        """Produce deterministic character-window chunks with full token and provenance fields."""
        text = str(item.get("text", "") or "")
        metadata = dict(item.get("metadata", {}))
        source = str(item.get("source", "unknown"))
        source_id = str(metadata.get("source_id") or make_source_id(source))
        url = str(item.get("url", ""))
        title = str(item.get("title", ""))
        published_at = str(item.get("published_at", ""))
        retrieved_at = str(metadata.get("retrieved_at") or datetime.now(UTC).isoformat())
        event_id = str(metadata.get("event_id", ""))
        content_id = str(metadata.get("content_id") or make_content_id(source_id, url, title, published_at, text))

        micro_topic_ids = []
        if metadata.get("micro_topic_id"):
            micro_topic_ids.append(str(metadata["micro_topic_id"]))
        for m in metadata.get("micro_topic_matches", []):
            if isinstance(m, dict) and m.get("micro_topic_id"):
                micro_topic_ids.append(str(m["micro_topic_id"]))
        micro_topic_ids = list(dict.fromkeys(micro_topic_ids))

        stride = max(1, chunk_size - chunk_overlap)
        windows = [
            (idx, min(len(text), idx + chunk_size), text[idx : idx + chunk_size])
            for idx in range(0, max(1, len(text)), stride)
        ] or [(0, 0, "")]

        chunks: list[dict[str, Any]] = []
        for idx, (start_offset, end_offset, chunk_text) in enumerate(windows):
            chunk_hash = hashlib.sha256(f"{content_id}:{start_offset}:{end_offset}".encode("utf-8")).hexdigest()[:12]
            chunk_id = f"chunk-{chunk_hash}"
            token_estimate = estimate_tokens(chunk_text)

            prov = provenance_from_mapping(
                item,
                EvidenceType.TRANSCRIPT if item.get("kind") == "youtube" else EvidenceType.ARTICLE,
                chunk_text[:200],
            )

            chunk_dict = {
                "id": chunk_id,
                "chunk_id": chunk_id,
                "content_id": content_id,
                "source_id": source_id,
                "event_id": event_id,
                "micro_topic_ids": micro_topic_ids,
                "start_offset": start_offset,
                "end_offset": end_offset,
                "text": chunk_text,
                "token_estimate": token_estimate,
                "published_at": published_at,
                "retrieved_at": retrieved_at,
                "provenance": prov.to_dict(),
                "metadata": {
                    **metadata,
                    "content_id": content_id,
                    "source_id": source_id,
                    "event_id": event_id,
                    "span_id": chunk_id,
                    "span_start": start_offset,
                    "span_end": end_offset,
                    "token_estimate": token_estimate,
                    "published_at": published_at,
                    "retrieved_at": retrieved_at,
                    "micro_topic_matches": [{"micro_topic_id": m} for m in micro_topic_ids],
                },
            }
            chunks.append(chunk_dict)
        return chunks

    @classmethod
    def semantic(cls, item: dict[str, Any]) -> list[dict[str, Any]]:
        """Semantic-compatible chunking interface; falls back cleanly to deterministic paragraphs."""
        return cls.deterministic(item, chunk_size=1200, chunk_overlap=120)
