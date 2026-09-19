"""Persistent evidence store decoupled from indexing and retrieval."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class EvidenceStore(Protocol):
    """Protocol for durable evidence records persistence."""

    def save_chunk(self, chunk: dict[str, Any]) -> None:
        ...

    def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        ...

    def list_chunks(self) -> list[dict[str, Any]]:
        ...


@dataclass
class LocalEvidenceStore:
    """File-system backed evidence store maintaining immutable evidence chunks."""

    storage_dir: Path
    _memory_cache: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._load_existing()

    def _load_existing(self) -> None:
        for file_path in self.storage_dir.glob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "id" in data:
                    self._memory_cache[data["id"]] = data
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "id" in item:
                            self._memory_cache[item["id"]] = item
            except Exception:
                continue

    def save_chunk(self, chunk: dict[str, Any]) -> None:
        chunk_id = chunk.get("id") or chunk.get("chunk_id")
        if not chunk_id:
            raise ValueError("Evidence chunk must have an id")
        self._memory_cache[chunk_id] = chunk
        target_path = self.storage_dir / f"{chunk_id}.json"
        tmp_path = self.storage_dir / f"{chunk_id}.json.tmp"
        tmp_path.write_text(json.dumps(chunk, indent=2), encoding="utf-8")
        tmp_path.replace(target_path)

    def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        return self._memory_cache.get(chunk_id)

    def list_chunks(self) -> list[dict[str, Any]]:
        return list(self._memory_cache.values())
