"""Multi-factor composite deterministic ranking for RAG candidate chunks."""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from .query import RetrievalRequest


def _terms(value: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9+._-]{1,}", value.lower())


def rank_evidence_chunks(
    chunks: list[dict[str, Any]],
    request: RetrievalRequest,
    *,
    limit: int = 4,
    corroboration_counts: dict[str, int] | None = None,
    conflicting_event_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Rank chunks using multi-factor explicit scoring with labeled components."""
    if not chunks:
        return []

    corroboration_counts = corroboration_counts or {}
    conflicting_event_ids = conflicting_event_ids or set()
    query_terms = set(_terms(request.query))
    count = max(1, len(chunks))
    doc_freq = Counter(term for chunk in chunks for term in set(_terms(chunk.get("text", ""))))

    now = datetime.now(UTC)
    ranked = []

    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        text = chunk.get("text", "")
        text_lower = text.lower()
        chunk_terms = Counter(_terms(text))

        # 1. Lexical score
        if query_terms:
            tf_idf_raw = sum(
                (1 + count / (1 + doc_freq[term])) * min(chunk_terms[term], 3)
                for term in query_terms
            )
            lexical_score = min(1.0, round(tf_idf_raw / max(1, len(query_terms) * 4), 3))
        else:
            lexical_score = 0.5

        # 2. Micro-topic score
        matches = metadata.get("micro_topic_matches", [])
        micro_topic_match = next(
            (m for m in matches if isinstance(m, dict) and m.get("micro_topic_id") == request.micro_topic_id),
            None,
        )
        if micro_topic_match:
            micro_topic_score = round(float(micro_topic_match.get("score", 0.9)), 3)
        elif metadata.get("micro_topic_id") == request.micro_topic_id:
            micro_topic_score = 0.9
        elif request.micro_topic_id and request.micro_topic_id.lower() in text_lower:
            micro_topic_score = 0.75
        else:
            micro_topic_score = 0.4

        # 3. Required concept match
        if request.required_concepts:
            matched_concepts = sum(
                1 for c in request.required_concepts if c.lower() in text_lower
            )
            concept_score = round(matched_concepts / len(request.required_concepts), 3)
        else:
            concept_score = 1.0

        # 4. Source trust score
        trust_tier = int(metadata.get("trust_tier", 4) or 4)
        source_score = round(max(0.2, (5 - trust_tier) / 4), 3)

        # 5. Freshness score
        raw_published = metadata.get("published_at")
        freshness_score = 0.5
        if raw_published:
            try:
                published = datetime.fromisoformat(str(raw_published).replace("Z", "+00:00")).astimezone(UTC)
                age_days = (now - published).total_seconds() / 86400
                freshness_score = max(0.0, round(1.0 - min(age_days / 30.0, 1.0), 3))
            except (ValueError, TypeError):
                freshness_score = 0.5

        # 6. Corroboration score
        event_id = str(metadata.get("event_id", ""))
        event_count = corroboration_counts.get(event_id, 1)
        corroboration_score = min(1.0, round(event_count / 3.0, 3))

        # 7. Duplicate & Conflict Penalties
        duplicate_penalty = 0.0
        if metadata.get("is_duplicate"):
            duplicate_penalty = 0.3

        conflict_penalty = 0.0
        if event_id and event_id in conflicting_event_ids:
            conflict_penalty = 0.25

        # Weighted final score computation
        raw_final = (
            0.30 * lexical_score
            + 0.25 * micro_topic_score
            + 0.15 * concept_score
            + 0.15 * source_score
            + 0.10 * freshness_score
            + 0.05 * corroboration_score
            - duplicate_penalty
            - conflict_penalty
        )
        final_score = max(0.0, min(1.0, round(raw_final, 3)))

        score_components = {
            "lexical_score": lexical_score,
            "micro_topic_score": micro_topic_score,
            "concept_score": concept_score,
            "source_score": source_score,
            "freshness_score": freshness_score,
            "corroboration_score": corroboration_score,
            "duplicate_penalty": duplicate_penalty,
            "conflict_penalty": conflict_penalty,
            "final_score": final_score,
        }

        ranked.append({
            **chunk,
            "score": final_score,
            "ranking_details": score_components,
        })

    # Sort descending by final score
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:limit]
