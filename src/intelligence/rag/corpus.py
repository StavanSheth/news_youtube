"""Repository-native evidence corpus interface and implementation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from ..contracts import EvidenceType, provenance_from_mapping
from ..identity import make_content_id, make_source_id
from ..microtopics import score_micro_topic_chunk
from .index import EvidenceIndex
from .query import RetrievalRequest
from .retrieval import HybridRetriever


def deterministic_chunks(item: dict[str, Any], size: int = 1400, overlap: int = 180) -> list[dict[str, Any]]:
    """Split text using deterministic character windows; this is not semantic chunking."""
    text = item.get("text", "") or ""
    stride = max(1, size - overlap)
    chunks = [text[index : index + size] for index in range(0, max(1, len(text)), stride)] or [""]
    source_id = item.get("metadata", {}).get("source_id") or make_source_id(item.get("source", "unknown"))
    content_id = item.get("metadata", {}).get("content_id") or make_content_id(
        source_id, item.get("url", ""), item.get("title", ""), item.get("published_at", ""), text
    )
    evidence_type = "transcript" if item.get("kind") == "youtube" else "article"
    retrieved_at = item.get("metadata", {}).get("retrieved_at") or datetime.now(UTC).isoformat()
    provenance_type = EvidenceType.TRANSCRIPT if item.get("kind") == "youtube" else EvidenceType.ARTICLE
    result = []
    classifications = []
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

    for index, chunk in enumerate(chunks):
        provenance = None
        if item.get("url", "").startswith(("http://", "https://")):
            provenance = provenance_from_mapping(
                {**item, "metadata": {**item.get("metadata", {}), "content_id": content_id, "source_id": source_id, "retrieved_at": retrieved_at}},
                provenance_type,
                chunk,
            ).to_dict()
        micro_topic_matches = []
        last_match: dict[str, Any] = {}
        for cls in classifications:
            match = score_micro_topic_chunk(chunk, cls)
            last_match = match
            if match.get("relevant"):
                micro_topic_id = str(cls.get("micro_topic_id") or cls.get("micro_topic", ""))
                micro_topic_slug = str(cls.get("micro_topic", ""))
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
        result.append({
            "id": f"{content_id}:{index}",
            "text": chunk,
            "metadata": {
                key: item.get(key, "")
                for key in ("id", "url", "source", "title", "kind", "published_at")
            }
            | {
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
                "span_id": f"{content_id}:span:{index * stride}:{min(len(text), index * stride + len(chunk))}",
                "micro_topic_match": last_match,
                "evidence_span_ids": [],
            },
        })
    return result


def semantic_chunks(item: dict[str, Any], size: int = 1400, overlap: int = 180) -> list[dict[str, Any]]:
    """Backward-compatible name for deterministic character-window chunking."""
    return deterministic_chunks(item, size, overlap)


class EvidenceCorpus(Protocol):
    """Protocol for evidence indexing and retrieval."""

    def add_item(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        """Chunk and index an item into the corpus."""
        ...

    def search(self, query: RetrievalRequest) -> list[dict[str, Any]]:
        """Return candidate evidence chunks matching query filters."""
        ...


@dataclass
class RepositoryEvidenceCorpus:
    """Repository-native corpus storing candidates backed by BM25 and dense multi-indexing."""

    storage_dir: Path | None = None
    chunk_size: int = 1400
    chunk_overlap: int = 180
    _chunks: list[dict[str, Any]] = field(default_factory=list)
    _indexed_content_ids: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.index = EvidenceIndex()
        self.retriever = HybridRetriever(self.index)
        if self.storage_dir and self.storage_dir.is_dir():
            self._load_from_storage()

    def _load_from_storage(self) -> None:
        if not self.storage_dir:
            return
        rag_files = list(self.storage_dir.glob("*.json"))
        for file_path in rag_files:
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for chunk in data:
                        if isinstance(chunk, dict) and "text" in chunk:
                            self._add_chunk(chunk)
                elif isinstance(data, dict) and "chunks" in data:
                    for chunk in data["chunks"]:
                        if isinstance(chunk, dict) and "text" in chunk:
                            self._add_chunk(chunk)
            except (OSError, json.JSONDecodeError):
                continue

    def _add_chunk(self, chunk: dict[str, Any]) -> None:
        metadata = chunk.get("metadata", {})
        content_id = metadata.get("content_id")
        chunk_id = chunk.get("id")
        # Prevent exact duplicate chunk insertions, but merge micro-topic authorizations
        for idx, existing in enumerate(self._chunks):
            if existing.get("id") == chunk_id:
                if existing.get("text") == chunk.get("text"):
                    existing_matches = existing.setdefault("metadata", {}).setdefault("micro_topic_matches", [])
                    new_matches = chunk.get("metadata", {}).get("micro_topic_matches", [])
                    for nm in new_matches:
                        if not any(em.get("micro_topic_id") == nm.get("micro_topic_id") for em in existing_matches):
                            existing_matches.append(nm)
                    self.index.add(existing)
                    return
                else:
                    self._chunks[idx] = chunk
                    self.index.add(chunk)
                    return
        self._chunks.append(chunk)
        self.index.add(chunk)
        if content_id:
            self._indexed_content_ids.add(content_id)

    def add_item(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        chunks = semantic_chunks(item, size=self.chunk_size, overlap=self.chunk_overlap)
        for chunk in chunks:
            self._add_chunk(chunk)
        return chunks

    def add_chunks(self, chunks: list[dict[str, Any]]) -> None:
        for chunk in chunks:
            self._add_chunk(chunk)

    def search(self, query: RetrievalRequest) -> list[dict[str, Any]]:
        """Return candidate chunks using indexed hybrid BM25 and dense retrieval."""
        top_k = max(20, getattr(query, "top_k", 4) * 5)
        candidates = self.retriever.retrieve_candidates(query, top_k=top_k)
        if not candidates:
            # Fallback to micro-topic scoped candidates or entity search if available
            candidates = self.index.search_by_micro_topic(query.micro_topic_id, top_k=top_k)
        # Ensure metadata contains copies to avoid cross-chunk mutation
        res = []
        for chunk in candidates:
            meta = dict(chunk.get("metadata", {}))
            if "micro_topic_matches" in meta:
                meta["micro_topic_matches"] = list(meta["micro_topic_matches"])
            res.append({**chunk, "metadata": meta})
        return res

    @property
    def total_chunks(self) -> int:
        return len(self._chunks)
