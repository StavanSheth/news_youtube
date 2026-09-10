"""Lightweight, deterministic retrieval for bounded micro-topic analysis."""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from .contracts import EvidenceType, provenance_from_mapping
from .identity import make_content_id, make_source_id


def _terms(value: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9+._-]{1,}", value.lower())


def semantic_chunks(item: dict[str, Any], size: int = 1400, overlap: int = 180) -> list[dict[str, Any]]:
    """Split text on a bounded window while retaining source/event metadata."""
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
    for index, chunk in enumerate(chunks):
        provenance = None
        if item.get("url", "").startswith(("http://", "https://")):
            provenance = provenance_from_mapping(
                {**item, "metadata": {**item.get("metadata", {}), "content_id": content_id, "source_id": source_id, "retrieved_at": retrieved_at}},
                provenance_type,
                chunk,
            ).to_dict()
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
            },
        })
    return result


def retrieve(
    chunks: list[dict[str, Any]], query: str, limit: int = 4,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Rank chunks with lexical scoring, metadata filters, and a deterministic rerank."""
    query_terms = set(_terms(query))
    if not query_terms:
        return []
    filters = filters or {}
    filtered = []
    for chunk in chunks:
        metadata = chunk.get("metadata", {})
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
        terms = Counter(_terms(chunk["text"]))
        score = sum((1 + count / (1 + document_frequency[term])) * min(terms[term], 3) for term in query_terms)
        trust_tier = int(chunk.get("metadata", {}).get("trust_tier", 4) or 4)
        score += max(0, 5 - trust_tier) * 0.15
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


class RAGManager:
    """Repository-compatible retrieval manager with an explicit evidence packet."""

    def __init__(self, settings: dict[str, Any]) -> None:
        self.settings = settings
        self.metrics = {"retrievals": 0, "chunks_indexed": 0, "chunks_selected": 0, "failures": 0}

    def retrieve(
        self,
        item: dict[str, Any],
        classification: dict[str, Any],
        theme: dict[str, Any],
        event_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.metrics["retrievals"] += 1
        try:
            chunks = semantic_chunks(
                item,
                int(self.settings.get("retrieval_chunk_size", 1400)),
                int(self.settings.get("retrieval_chunk_overlap", 180)),
            )
            self.metrics["chunks_indexed"] += len(chunks)
            query = " ".join(
                filter(None, [
                    micro_topic_query(classification),
                    theme.get("id", ""),
                    " ".join(theme.get("questions", [])),
                    " ".join(event_context.get("entities", [])) if event_context else "",
                ])
            )
            selected = retrieve(
                chunks,
                query,
                min(int(self.settings.get("retrieval_top_k", 4)), 8),
                filters={"kind": item.get("kind")} if item.get("kind") else None,
            )
            self.metrics["chunks_selected"] += len(selected)
            return {
                "micro_topic": classification.get("micro_topic", ""),
                "query": query,
                "chunks": selected,
                "status": "OK" if selected else "EMPTY_RETRIEVAL",
            }
        except Exception as error:
            self.metrics["failures"] += 1
            return {
                "micro_topic": classification.get("micro_topic", ""),
                "query": "",
                "chunks": [],
                "status": "RETRIEVAL_FAILURE",
                "error_type": type(error).__name__,
            }
