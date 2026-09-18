"""Authoritative scoped EvidenceIndex using BM25 and local deterministic dense vectors."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any

from rank_bm25 import BM25L


def tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric terms."""
    return [t for t in re.findall(r"[a-z0-9_]{2,}", text.lower()) if t not in {"the", "and", "for", "with", "this", "that"}]


def compute_dense_vector(text: str, dim: int = 64) -> list[float]:
    """Compute deterministic, local dense pseudo-embedding without network dependencies."""
    tokens = tokenize(text)
    if not tokens:
        return [0.0] * dim
    vec = [0.0] * dim
    for token in tokens:
        # Hash token into bucket and sign
        h = hash(token)
        idx = abs(h) % dim
        sign = 1.0 if (h % 2 == 0) else -1.0
        vec[idx] += sign
    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    return max(0.0, min(1.0, sum(a * b for a, b in zip(v1, v2, strict=False))))


class EvidenceIndex:
    """Scoped multi-index for micro-topic, lexical BM25, and local dense candidate retrieval."""

    def __init__(self) -> None:
        self._chunks: dict[str, dict[str, Any]] = {}
        self._content_to_chunks: dict[str, set[str]] = defaultdict(set)
        self._micro_topic_index: dict[str, set[str]] = defaultdict(set)
        self._entity_index: dict[str, set[str]] = defaultdict(set)
        self._event_index: dict[str, set[str]] = defaultdict(set)
        self._bm25: BM25L | None = None
        self._bm25_chunk_ids: list[str] = []
        self._dense_vectors: dict[str, list[float]] = {}
        self._dirty = False

    def add(self, chunk: dict[str, Any]) -> None:
        """Add and index an evidence chunk."""
        chunk_id = str(chunk.get("id", ""))
        if not chunk_id:
            return
        self._chunks[chunk_id] = chunk
        meta = chunk.get("metadata", {})

        content_id = meta.get("content_id")
        if content_id:
            self._content_to_chunks[str(content_id)].add(chunk_id)

        # Micro-topic inverted index
        matches = meta.get("micro_topic_matches", [])
        for m in matches:
            if isinstance(m, dict):
                mt_id = m.get("micro_topic_id") or m.get("micro_topic")
                if mt_id:
                    self._micro_topic_index[str(mt_id)].add(chunk_id)
        if meta.get("micro_topic_id"):
            self._micro_topic_index[str(meta["micro_topic_id"])].add(chunk_id)

        # Entity index
        entity_ids = meta.get("entity_ids", []) or meta.get("entities", [])
        for eid in entity_ids:
            if eid:
                self._entity_index[str(eid).lower()].add(chunk_id)

        # Event index
        event_id = meta.get("event_id")
        if event_id:
            self._event_index[str(event_id)].add(chunk_id)

        # Dense vector
        self._dense_vectors[chunk_id] = compute_dense_vector(chunk.get("text", ""))
        self._dirty = True

    def remove(self, content_id: str) -> None:
        """Remove all chunks associated with a content_id."""
        chunk_ids = list(self._content_to_chunks.pop(content_id, set()))
        for cid in chunk_ids:
            self._chunks.pop(cid, None)
            self._dense_vectors.pop(cid, None)
            for s in self._micro_topic_index.values():
                s.discard(cid)
            for s in self._entity_index.values():
                s.discard(cid)
            for s in self._event_index.values():
                s.discard(cid)
        self._dirty = True

    def _ensure_bm25(self) -> None:
        if self._dirty or self._bm25 is None:
            self._bm25_chunk_ids = list(self._chunks.keys())
            corpus_tokens = [
                tokenize(self._chunks[cid].get("text", ""))
                for cid in self._bm25_chunk_ids
            ]
            if corpus_tokens and any(corpus_tokens):
                self._bm25 = BM25L(corpus_tokens)
            else:
                self._bm25 = None
            self._dirty = False

    def search_lexical(self, query: str, top_k: int = 10) -> list[tuple[dict[str, Any], float]]:
        """Lexical search using BM25L over indexed chunks."""
        self._ensure_bm25()
        if not self._bm25 or not self._bm25_chunk_ids:
            return []
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        scores = self._bm25.get_scores(query_tokens)
        query_set = set(query_tokens)
        results = []
        for cid, score in zip(self._bm25_chunk_ids, scores, strict=False):
            if score > 0:
                chunk = self._chunks[cid]
                chunk_tokens = tokenize(chunk.get("text", ""))
                if query_set.intersection(chunk_tokens):
                    results.append((chunk, float(score)))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def search_dense(self, query: str, top_k: int = 10) -> list[tuple[dict[str, Any], float]]:
        """Dense semantic search using cosine similarity over local vectors."""
        query_vec = compute_dense_vector(query)
        results = []
        for cid, chunk in self._chunks.items():
            cvec = self._dense_vectors.get(cid)
            if cvec:
                sim = cosine_similarity(query_vec, cvec)
                if sim > 0:
                    results.append((chunk, sim))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def search_by_micro_topic(self, micro_topic_id: str, top_k: int = 10) -> list[dict[str, Any]]:
        """Scoped search returning chunks authorized for micro_topic_id."""
        cids = self._micro_topic_index.get(str(micro_topic_id), set())
        return [self._chunks[cid] for cid in cids if cid in self._chunks][:top_k]

    def search_by_entity(self, entity_id: str, top_k: int = 10) -> list[dict[str, Any]]:
        cids = self._entity_index.get(str(entity_id).lower(), set())
        return [self._chunks[cid] for cid in cids if cid in self._chunks][:top_k]

    def search_by_event(self, event_id: str, top_k: int = 10) -> list[dict[str, Any]]:
        cids = self._event_index.get(str(event_id), set())
        return [self._chunks[cid] for cid in cids if cid in self._chunks][:top_k]

    def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        return self._chunks.get(chunk_id)

    @property
    def total_chunks(self) -> int:
        return len(self._chunks)
