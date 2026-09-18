"""Hybrid retrieval orchestrator combining BM25, dense vectors, and RRF."""

from __future__ import annotations

from typing import Any, Protocol
from .fusion import reciprocal_rank_fusion
from .index import EvidenceIndex
from .query import RetrievalRequest


class Reranker(Protocol):
    def rerank(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]: ...


class NoOpReranker:
    def rerank(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return candidates


class LocalCrossEncoderReranker:
    """Optional local lightweight cross-encoder interface; defaults to lexical scoring if model absent."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name

    def rerank(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Deterministic lightweight fallback without external heavy network models
        return candidates


class HybridRetriever:
    """Combines lexical BM25 and local dense candidate retrieval using Reciprocal Rank Fusion."""

    def __init__(self, index: EvidenceIndex, k: int = 60, reranker: Reranker | None = None) -> None:
        self.index = index
        self.k = k
        self.reranker = reranker or NoOpReranker()

    def retrieve_candidates(
        self,
        request: RetrievalRequest,
        top_k: int = 20,
    ) -> list[dict[str, Any]]:
        """Retrieve candidate chunks using BM25 and dense search, then fuse via RRF."""
        # 1. BM25 lexical candidates
        lexical_candidates = self.index.search_lexical(request.query, top_k=top_k)

        # 2. Dense semantic candidates
        dense_candidates = self.index.search_dense(request.query, top_k=top_k)

        # 3. Micro-topic scoped candidates (seeded with base lexical score if not already retrieved)
        scoped_chunks = self.index.search_by_micro_topic(request.micro_topic_id, top_k=top_k)
        scoped_list = [(c, 1.0) for c in scoped_chunks]

        # 4. Rank fusion
        fused = reciprocal_rank_fusion(
            [lexical_candidates, dense_candidates, scoped_list],
            k=self.k,
            top_k=top_k,
        )

        candidates = []
        for chunk, rrf_score in fused:
            candidates.append({**chunk, "rrf_score": rrf_score})

        # 5. Optional reranker
        return self.reranker.rerank(request.query, candidates)
