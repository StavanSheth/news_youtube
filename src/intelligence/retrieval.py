"""Lightweight, deterministic retrieval for bounded micro-topic analysis."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from .contracts import EvidenceType, provenance_from_mapping
from .identity import make_content_id, make_source_id
from .evidence_scope import EvidenceScope
from .microtopics import score_micro_topic_chunk
from .statuses import IntelligenceStatus


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
class RetrievalRequest:
    query: str
    micro_topic_id: str
    theme_id: str
    retrieval_intent: dict[str, Any] = field(default_factory=dict)
    preferred_source_types: tuple[str, ...] = ()
    evidence_types: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    freshness: str = "30d"
    max_results: int = 4
    max_context: int = 12000

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query, "micro_topic_id": self.micro_topic_id, "theme_id": self.theme_id,
            "retrieval_intent": self.retrieval_intent, "preferred_source_types": list(self.preferred_source_types),
            "evidence_types": list(self.evidence_types), "exclusions": list(self.exclusions),
            "freshness": self.freshness, "max_results": self.max_results, "max_context": self.max_context,
        }


@dataclass(frozen=True)
class RetrievalResult:
    request: RetrievalRequest | None = None
    chunks: tuple[dict[str, Any], ...] = ()
    status: str = "OK"
    error_type: str | None = None


def _terms(value: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9+._-]{1,}", value.lower())


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
    classification = item.get("metadata", {}).get("classification", {})
    for index, chunk in enumerate(chunks):
        provenance = None
        if item.get("url", "").startswith(("http://", "https://")):
            provenance = provenance_from_mapping(
                {**item, "metadata": {**item.get("metadata", {}), "content_id": content_id, "source_id": source_id, "retrieved_at": retrieved_at}},
                provenance_type,
                chunk,
            ).to_dict()
        match = score_micro_topic_chunk(chunk, classification) if classification else {}
        micro_topic_matches = []
        configured_threshold = classification.get("secondary_threshold", classification.get("classification_threshold"))
        is_authorized = match.get("relevant") if configured_threshold is None else match.get("score", 0) >= float(configured_threshold)
        if classification and match.get("matched_signals") and is_authorized:
            micro_topic_matches.append({
                "micro_topic_id": classification.get("micro_topic_id", classification.get("micro_topic", "")),
                "score": match["score"], "matched_signals": match["matched_signals"],
                "matched_groups": match.get("matched_signal_groups", {}), "confidence": match["score"],
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
                "micro_topic_id": "",
                "micro_topic_matches": micro_topic_matches,
                "span_id": f"{content_id}:span:{index * stride}:{min(len(text), index * stride + len(chunk))}",
                "micro_topic_match": match,
                "evidence_span_ids": [],
            },
        })
    return result


def semantic_chunks(item: dict[str, Any], size: int = 1400, overlap: int = 180) -> list[dict[str, Any]]:
    """Backward-compatible name for deterministic character-window chunking."""
    return deterministic_chunks(item, size, overlap)


def _freshness_days(value: str) -> int | None:
    match = re.fullmatch(r"(\d+)d", str(value or "").strip().lower())
    return int(match.group(1)) if match else None


def filter_freshness(chunks: list[dict[str, Any]], freshness: str, *, now: datetime | None = None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Filter only parseable old timestamps; retain missing/invalid/future dates with diagnostics."""
    days = _freshness_days(freshness)
    diagnostics = {"freshness_filtered_count": 0, "freshness_missing_count": 0, "freshness_invalid_count": 0, "freshness_future_count": 0}
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
    chunks: list[dict[str, Any]], query: str, limit: int = 4,
    filters: dict[str, Any] | None = None, retrieval_intent: RetrievalIntent | None = None,
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
    """Normalize structured theme/profile retrieval intent for the retriever."""
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


class RAGManager:
    """Repository-compatible retrieval manager with an explicit evidence packet."""

    def __init__(self, settings: dict[str, Any]) -> None:
        self.settings = settings
        self.metrics = {"retrievals": 0, "chunks_indexed": 0, "chunks_selected": 0, "failures": 0, "chunks_before_scope": 0, "chunks_after_scope": 0, "chunks_rejected_scope": 0, "scope_rejection_rate": 0.0}

    def retrieve(
        self,
        item: dict[str, Any],
        classification: dict[str, Any],
        theme: dict[str, Any],
        event_context: dict[str, Any] | None = None,
        scope: EvidenceScope | None = None,
    ) -> dict[str, Any]:
        self.metrics["retrievals"] += 1
        try:
            chunks = semantic_chunks(
                item,
                int(self.settings.get("retrieval_chunk_size", 1400)),
                int(self.settings.get("retrieval_chunk_overlap", 180)),
            )
            self.metrics["chunks_indexed"] += len(chunks)
            before_scope = len(chunks)
            if scope is not None:
                chunks = [chunk for chunk in chunks if scope.allows(chunk)]
            after_scope = len(chunks)
            rejected_scope = before_scope - after_scope
            scope_rejected_all = bool(scope is not None and before_scope and not chunks)
            self.metrics["chunks_before_scope"] += before_scope
            self.metrics["chunks_after_scope"] += after_scope
            self.metrics["chunks_rejected_scope"] += rejected_scope
            self.metrics["scope_rejection_rate"] = round(self.metrics["chunks_rejected_scope"] / max(1, self.metrics["chunks_before_scope"]), 3)
            retrieval_intent = build_retrieval_intent(classification, theme)
            intent = RetrievalIntent.from_mapping(retrieval_intent)
            retrieval_intent = intent.to_dict()
            chunks, freshness_diagnostics = filter_freshness(chunks, intent.freshness)
            query = " ".join(
                filter(None, [
                    micro_topic_query(classification),
                    " ".join(intent.required_concepts),
                    " ".join(intent.evidence_types),
                    " ".join(intent.preferred_source_types),
                    " ".join(event_context.get("entities", [])) if event_context else "",
                ])
            )
            request = RetrievalRequest(
                query=query,
                micro_topic_id=str(classification.get("micro_topic_id", classification.get("micro_topic", ""))),
                theme_id=str(theme.get("theme_id", theme.get("id", ""))),
                retrieval_intent=retrieval_intent,
                preferred_source_types=intent.preferred_source_types,
                evidence_types=intent.evidence_types,
                exclusions=intent.exclusion_concepts,
                freshness=intent.freshness,
                max_results=min(int(self.settings.get("retrieval_top_k", 4)), 8),
                max_context=int(self.settings.get("max_retrieved_context_chars", 12000)),
            )
            selected = retrieve(
                chunks,
                request.query,
                request.max_results,
                filters={"kind": item.get("kind")} if item.get("kind") else None,
                retrieval_intent=intent,
            )
            self.metrics["chunks_selected"] += len(selected)
            return {
                "micro_topic": classification.get("micro_topic", ""),
                "query": query,
                "chunks": selected,
                "status": "OK" if selected else (IntelligenceStatus.NO_RELEVANT_CONTENT.value if scope_rejected_all else IntelligenceStatus.INSUFFICIENT_EVIDENCE.value),
                "retrieval_intent": retrieval_intent,
                "retrieval_request": request.to_dict(),
                "diagnostics": {
                    **freshness_diagnostics,
                    "before_scope": before_scope,
                    "after_scope": after_scope,
                    "rejected_scope": rejected_scope,
                    "scope_rejection_rate": round(rejected_scope / max(1, before_scope), 3),
                },
            }
        except (KeyError, TypeError, ValueError, OSError, RuntimeError) as error:
            self.metrics["failures"] += 1
            return {
                "micro_topic": classification.get("micro_topic", ""),
                "query": "",
                "chunks": [],
                "status": IntelligenceStatus.RETRIEVAL_FAILURE.value,
                "error_type": type(error).__name__,
            }
