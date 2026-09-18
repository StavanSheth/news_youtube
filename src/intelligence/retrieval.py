"""Authoritative retrieval compatibility facade delegating completely to intelligence.rag."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from .rag.corpus import deterministic_chunks, semantic_chunks
from .rag.manager import ProductionRAGManager
from .rag.query import RetrievalRequest

RAGManager = ProductionRAGManager


def _terms(value: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9+._-]{1,}", value.lower())


@dataclass(frozen=True)
class RetrievalIntent:
    required_concepts: tuple[str, ...] = ()
    preferred_source_types: tuple[str, ...] = ()
    evidence_types: tuple[str, ...] = ()
    exclusion_concepts: tuple[str, ...] = ()
    freshness: str = "30d"

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "RetrievalIntent":
        return cls(
            required_concepts=tuple(str(item) for item in value.get("required_concepts", [])),
            preferred_source_types=tuple(str(item) for item in value.get("preferred_source_types", [])),
            evidence_types=tuple(str(item) for item in value.get("evidence_types", [])),
            exclusion_concepts=tuple(str(item) for item in value.get("exclusion_concepts", [])),
            freshness=str(value.get("freshness", "30d")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "required_concepts": list(self.required_concepts),
            "preferred_source_types": list(self.preferred_source_types),
            "evidence_types": list(self.evidence_types),
            "exclusion_concepts": list(self.exclusion_concepts),
            "freshness": self.freshness,
        }


@dataclass(frozen=True)
class RetrievalResult:
    request: RetrievalRequest | None = None
    chunks: tuple[dict[str, Any], ...] = ()
    status: str = "OK"
    error_type: str | None = None


def _freshness_days(value: str) -> int | None:
    match = re.fullmatch(r"(\d+)d", str(value or "").strip().lower())
    return int(match.group(1)) if match else None


def filter_freshness(
    chunks: list[dict[str, Any]],
    freshness: str,
    *,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Filter only parseable old timestamps; retain missing/invalid/future dates with diagnostics."""
    days = _freshness_days(freshness)
    diagnostics = {
        "freshness_filtered_count": 0,
        "freshness_missing_count": 0,
        "freshness_invalid_count": 0,
        "freshness_future_count": 0,
    }
    if days is None:
        return chunks, diagnostics
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=days)
    kept = []
    for chunk in chunks:
        raw = chunk.get("metadata", {}).get("published_at", "")
        if not raw:
            diagnostics["freshness_missing_count"] += 1
            kept.append(chunk)
            continue
        try:
            published = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if published.tzinfo is None or published.utcoffset() is None:
                raise ValueError
            published = published.astimezone(UTC)
        except (TypeError, ValueError):
            diagnostics["freshness_invalid_count"] += 1
            kept.append(chunk)
            continue
        if published > now:
            diagnostics["freshness_future_count"] += 1
            kept.append(chunk)
        elif published < cutoff:
            diagnostics["freshness_filtered_count"] += 1
        else:
            kept.append(chunk)
    return kept, diagnostics


def retrieve(
    chunks: list[dict[str, Any]],
    query: str,
    limit: int = 4,
    filters: dict[str, Any] | None = None,
    retrieval_intent: RetrievalIntent | None = None,
) -> list[dict[str, Any]]:
    """Rank chunks with lexical scoring, metadata filters, and a deterministic rerank."""
    query_terms = set(_terms(query))
    if not query_terms:
        return []
    filters = filters or {}
    filtered = []
    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        text_lower = chunk.get("text", "").lower()
        if retrieval_intent and any(str(term).lower() in text_lower for term in retrieval_intent.exclusion_concepts):
            continue
        if any(
            value and (
                metadata.get(key) != value
                if not isinstance(value, (list, tuple, set))
                else not set(value).intersection(metadata.get(key, []) if isinstance(metadata.get(key, []), list) else [metadata.get(key)])
            )
            for key, value in filters.items()
        ):
            continue
        filtered.append(chunk)
    chunks = filtered
    if not chunks:
        return []
    document_frequency = Counter(term for chunk in chunks for term in set(_terms(chunk["text"])))
    count = max(1, len(chunks))
    ranked = []
    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        terms = Counter(_terms(chunk["text"]))
        score = sum((1 + count / (1 + document_frequency[term])) * min(terms[term], 3) for term in query_terms)
        trust_tier = int(metadata.get("trust_tier", 4) or 4)
        score += max(0, 5 - trust_tier) * 0.15
        if retrieval_intent:
            score += sum(0.12 for term in retrieval_intent.required_concepts if str(term).lower() in chunk["text"].lower())
            source_type = str(metadata.get("source_type", metadata.get("kind", ""))).lower()
            if any(str(value).lower() == source_type for value in retrieval_intent.preferred_source_types):
                score += 0.08
            if any(str(value).lower() == str(metadata.get("evidence_type", "")).lower() for value in retrieval_intent.evidence_types):
                score += 0.08
        if score:
            ranked.append({**chunk, "score": round(score, 3)})
    return sorted(ranked, key=lambda entry: entry["score"], reverse=True)[:limit]


def micro_topic_query(classification: dict[str, Any]) -> str:
    return " ".join(
        str(value)
        for value in (
            classification.get("domain", ""),
            classification.get("topic", ""),
            classification.get("micro_topic", ""),
            *classification.get("signals", []),
        )
    )


def build_retrieval_intent(classification: dict[str, Any], theme: dict[str, Any]) -> dict[str, Any]:
    intent = dict(theme.get("retrieval_intent", {}) or {})
    profile_intent = classification.get("profile", {}).get("retrieval_intent", {}) if isinstance(classification.get("profile"), dict) else {}
    for key, value in profile_intent.items():
        if not intent.get(key):
            intent[key] = value
    intent.setdefault("required_concepts", [classification.get("micro_topic", "")])
    intent.setdefault("preferred_source_types", [])
    intent.setdefault("evidence_types", [])
    intent.setdefault("exclusion_concepts", [])
    intent.setdefault("freshness", "30d")
    return intent


__all__ = [
    "ProductionRAGManager",
    "RAGManager",
    "RetrievalIntent",
    "RetrievalRequest",
    "RetrievalResult",
    "build_retrieval_intent",
    "deterministic_chunks",
    "filter_freshness",
    "micro_topic_query",
    "retrieve",
    "semantic_chunks",
]
