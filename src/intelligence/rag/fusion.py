"""Reciprocal Rank Fusion (RRF) for hybrid retrieval combining BM25 and dense results."""

from __future__ import annotations

from typing import Any


def reciprocal_rank_fusion(
    rankings: list[list[tuple[dict[str, Any], float]]],
    k: int = 60,
    top_k: int = 10,
) -> list[tuple[dict[str, Any], float]]:
    """Compute Reciprocal Rank Fusion over multiple ranked candidate lists.

    Formula: RRF(d) = sum(1 / (k + rank(d))) for each ranked list where d appears.
    Rank is 1-indexed (1, 2, ...).
    """
    rrf_scores: dict[str, float] = {}
    chunk_map: dict[str, dict[str, Any]] = {}

    for ranked_list in rankings:
        for rank_zero_idx, (chunk, _) in enumerate(ranked_list):
            chunk_id = str(chunk.get("id", ""))
            if not chunk_id:
                continue
            chunk_map[chunk_id] = chunk
            rank_1_idx = rank_zero_idx + 1
            score = 1.0 / (k + rank_1_idx)
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + score

    sorted_results = sorted(
        [(chunk_map[cid], round(score, 6)) for cid, score in rrf_scores.items()],
        key=lambda x: (x[1], str(x[0].get("id", ""))),
        reverse=True,
    )
    return sorted_results[:top_k]
