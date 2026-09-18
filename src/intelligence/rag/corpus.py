"""Repository-native evidence corpus interface and implementation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from ..evidence.chunking import deterministic_chunks, semantic_chunks
from .index import EvidenceIndex
from .query import RetrievalRequest
from .retrieval import HybridRetriever


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


__all__ = [
    "EvidenceCorpus",
    "RepositoryEvidenceCorpus",
    "deterministic_chunks",
    "semantic_chunks",
]
