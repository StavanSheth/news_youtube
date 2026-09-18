"""Repository-native evidence corpus interface and implementation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from ..retrieval import RetrievalRequest, semantic_chunks


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
    """Repository-native corpus storing in-memory candidates backed by disk persistence."""

    storage_dir: Path | None = None
    chunk_size: int = 1400
    chunk_overlap: int = 180
    _chunks: list[dict[str, Any]] = field(default_factory=list)
    _indexed_content_ids: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
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
        # Prevent exact duplicate chunk insertions
        if any(existing.get("id") == chunk_id for existing in self._chunks):
            return
        self._chunks.append(chunk)
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
        """Return candidate chunks matching coarse query criteria."""
        candidates = []
        for chunk in self._chunks:
            # Candidates are passed to hard eligibility checks
            candidates.append(dict(chunk))
        return candidates

    @property
    def total_chunks(self) -> int:
        return len(self._chunks)
