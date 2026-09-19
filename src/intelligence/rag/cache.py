"""Deterministic retrieval caching keyed by query, micro-topic, cutoff, and versions."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RetrievalCacheKey:
    query_hash: str
    micro_topic_id: str
    edition_cutoff: str
    retrieval_config_version: str
    corpus_version: str
    taxonomy_version: str = "1.0.0"

    @classmethod
    def create(
        cls,
        query: str,
        micro_topic_id: str,
        edition_cutoff: datetime | str | None,
        retrieval_config_version: str = "1.0.0",
        corpus_version: str = "1.0.0",
        taxonomy_version: str = "1.0.0",
    ) -> "RetrievalCacheKey":
        query_hash = hashlib.sha256(str(query or "").strip().lower().encode("utf-8")).hexdigest()[:16]
        cutoff_str = str(edition_cutoff or "no_cutoff")
        return cls(
            query_hash=query_hash,
            micro_topic_id=str(micro_topic_id or "").strip(),
            edition_cutoff=cutoff_str,
            retrieval_config_version=str(retrieval_config_version),
            corpus_version=str(corpus_version),
            taxonomy_version=str(taxonomy_version),
        )

    def to_key(self) -> str:
        return f"{self.taxonomy_version}:{self.corpus_version}:{self.retrieval_config_version}:{self.micro_topic_id}:{self.edition_cutoff}:{self.query_hash}"


class RetrievalCache:
    """In-memory and file-compatible deterministic retrieval cache."""

    def __init__(self, max_entries: int = 500) -> None:
        self.max_entries = max_entries
        self._cache: dict[str, dict[str, Any]] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: RetrievalCacheKey) -> dict[str, Any] | None:
        cache_id = key.to_key()
        if cache_id in self._cache:
            self.hits += 1
            return dict(self._cache[cache_id])
        self.misses += 1
        return None

    def set(self, key: RetrievalCacheKey, value: dict[str, Any]) -> None:
        if len(self._cache) >= self.max_entries:
            # Evict oldest entry
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[key.to_key()] = dict(value)

    def invalidate(self) -> None:
        self._cache.clear()

    def stats(self) -> dict[str, Any]:
        total = self.hits + self.misses
        return {
            "size": len(self._cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 3) if total > 0 else 0.0,
        }
