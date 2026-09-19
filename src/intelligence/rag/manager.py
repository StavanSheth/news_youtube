"""Authoritative RAG Manager integrating corpus, eligibility, query, ranking, and diversity."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .budget import ContextBudgeter
from .cache import RetrievalCache, RetrievalCacheKey
from .corpus import EvidenceCorpus, RepositoryEvidenceCorpus
from .diversity import apply_diversity_filtering
from .eligibility import filter_eligible_candidates
from .packet import ContextPacket
from .query import RetrievalRequest, build_retrieval_request
from .ranking import rank_evidence_chunks
from ..evidence_scope import EvidenceScope
from ..statuses import IntelligenceStatus


@dataclass
class RetrievalResult(Mapping):
    """Authoritative retrieval result contract wrapping context packet and candidates."""

    status: str
    query: str
    micro_topic: str
    chunks: list[dict[str, Any]]
    context_packet: dict[str, Any]
    retrieval_request: dict[str, Any] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    rejection_reason: str | None = None
    retrieval_intent: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __getitem__(self, item: str) -> Any:
        if hasattr(self, item):
            return getattr(self, item)
        raise KeyError(item)

    def __iter__(self):
        yield from (
            "status",
            "query",
            "micro_topic",
            "chunks",
            "context_packet",
            "retrieval_request",
            "diagnostics",
            "rejection_reason",
            "retrieval_intent",
        )

    def __len__(self) -> int:
        return 9

    def __contains__(self, item: object) -> bool:
        return hasattr(self, str(item))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "query": self.query,
            "micro_topic": self.micro_topic,
            "chunks": list(self.chunks),
            "context_packet": self.context_packet,
            "retrieval_request": self.retrieval_request,
            "diagnostics": self.diagnostics,
            "rejection_reason": self.rejection_reason,
            "retrieval_intent": self.retrieval_intent,
        }


class ProductionRAGManager:
    """Production-grade RAG orchestrator executing the complete Set E pipeline."""

    def __init__(
        self,
        settings: dict[str, Any],
        corpus: EvidenceCorpus | None = None,
        cache: RetrievalCache | None = None,
    ) -> None:
        self.settings = settings
        self.cache = cache or RetrievalCache()
        self.corpus = corpus or RepositoryEvidenceCorpus(
            chunk_size=int(settings.get("retrieval_chunk_size", 1400)),
            chunk_overlap=int(settings.get("retrieval_chunk_overlap", 180)),
        )
        self.metrics = {
            "retrievals": 0,
            "chunks_indexed": 0,
            "chunks_selected": 0,
            "failures": 0,
            "chunks_before_scope": 0,
            "chunks_after_scope": 0,
            "chunks_rejected_scope": 0,
            "scope_rejection_rate": 0.0,
            "eligibility_rejections": 0,
            "diversity_skips": 0,
        }

    def index_item(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        chunks = self.corpus.add_item(item)
        self.metrics["chunks_indexed"] += len(chunks)
        return chunks

    def retrieve(
        self,
        request_or_item: RetrievalRequest | dict[str, Any],
        classification: dict[str, Any] | None = None,
        theme: dict[str, Any] | None = None,
        event_context: dict[str, Any] | None = None,
        scope: EvidenceScope | None = None,
        run_context: Any | None = None,
        edition_context: Any | None = None,
        publication_cutoff_utc: datetime | str | None = None,
    ) -> RetrievalResult:
        """Execute full RAG retrieval pipeline returning structured RetrievalResult."""
        self.metrics["retrievals"] += 1
        try:
            if isinstance(request_or_item, RetrievalRequest):
                request = request_or_item
                current_item = {"id": request.micro_topic_id, "title": request.query}
                before_scope = 0
                cutoff = request.publication_cutoff or publication_cutoff_utc
                classification = classification or {
                    "micro_topic_id": request.micro_topic_id,
                    "micro_topic": request.micro_topic_id,
                }
            else:
                current_item = request_or_item
                current_chunks = self.index_item(current_item)
                before_scope = len(current_chunks)
                classification = classification or {}
                theme = theme or {}

                budget_config = {
                    "max_rag_items": self.settings.get("retrieval_top_k", 4),
                    "max_context_chars": self.settings.get("max_retrieved_context_chars", 12000),
                }
                cutoff = publication_cutoff_utc
                if cutoff is None and edition_context is not None:
                    cutoff = getattr(edition_context, "publication_cutoff_utc", None)
                if cutoff is None and run_context is not None:
                    cutoff = getattr(run_context, "publication_cutoff_utc", None)
                if cutoff is None:
                    cutoff = datetime.now(UTC)
                elif isinstance(cutoff, str):
                    try:
                        parsed = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
                        cutoff = parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
                    except Exception:
                        cutoff = datetime.now(UTC)
                elif isinstance(cutoff, datetime) and (cutoff.tzinfo is None or cutoff.utcoffset() is None):
                    cutoff = cutoff.replace(tzinfo=UTC)

                request = build_retrieval_request(
                    micro_topic=classification.get("micro_topic_id") or classification.get("micro_topic", ""),
                    theme=theme,
                    classification=classification,
                    event_context=event_context,
                    cutoff=cutoff,
                    budget=budget_config,
                )

            cache_key = RetrievalCacheKey.create(
                query=request.query,
                micro_topic_id=request.micro_topic_id,
                edition_cutoff=cutoff,
            )
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                if isinstance(cached_result, RetrievalResult):
                    return cached_result
                return RetrievalResult(
                    status=cached_result.get("status", "OK"),
                    query=cached_result.get("query", ""),
                    micro_topic=cached_result.get("micro_topic", ""),
                    chunks=cached_result.get("chunks", []),
                    context_packet=cached_result.get("context_packet", {}),
                    retrieval_request=cached_result.get("retrieval_request", {}),
                    diagnostics=cached_result.get("diagnostics", {}),
                    rejection_reason=cached_result.get("rejection_reason"),
                    retrieval_intent=cached_result.get("retrieval_intent", {}),
                )

            # Step 3: Search candidates from corpus (current + historical)
            candidates = self.corpus.search(request)

            # Step 4: Apply EvidenceScope authorization if provided
            if scope is not None:
                scoped_candidates = [c for c in candidates if scope.allows(c)]
                rejected_scope = len(candidates) - len(scoped_candidates)
            else:
                scoped_candidates = candidates
                rejected_scope = 0

            self.metrics["chunks_before_scope"] += before_scope
            self.metrics["chunks_after_scope"] += len(scoped_candidates)
            self.metrics["chunks_rejected_scope"] += rejected_scope
            if self.metrics["chunks_before_scope"]:
                self.metrics["scope_rejection_rate"] = round(
                    self.metrics["chunks_rejected_scope"] / self.metrics["chunks_before_scope"], 3
                )

            # Step 5: Hard eligibility check before ranking (strictly rejecting quarantined sources)
            quarantined = set(self.settings.get("quarantined_sources", []))
            disabled = set(self.settings.get("disabled_sources", []))
            eligible_chunks, eligibility_diag = filter_eligible_candidates(
                scoped_candidates,
                request,
                publication_cutoff=cutoff,
                disabled_sources=disabled,
                quarantined_sources=quarantined,
            )
            self.metrics["eligibility_rejections"] += eligibility_diag.get("rejected_count", 0)

            # Step 6: Multi-factor composite ranking
            top_k = min(int(self.settings.get("retrieval_top_k", 4)), 8)
            ranked_chunks = rank_evidence_chunks(
                eligible_chunks,
                request,
                limit=top_k * 2,  # Oversample before diversity
            )

            # Step 7: Diversity enforcement
            selected_chunks, diversity_diag = apply_diversity_filtering(
                ranked_chunks,
                target_count=top_k,
            )

            # Step 7b: Enforce context character and token budget limit via ContextBudgeter
            max_chars = int(self.settings.get("max_retrieved_context_chars", 12000))
            max_tokens = int(self.settings.get("max_context_tokens", 3000))
            budgeter = ContextBudgeter(max_chars=max_chars, max_tokens=max_tokens, max_items=top_k)
            selected_chunks, budget_trace = budgeter.enforce_budget(selected_chunks)

            self.metrics["chunks_selected"] += len(selected_chunks)
            self.metrics["diversity_skips"] += diversity_diag.get("diversity_skipped", 0)

            # Step 8: Build ContextPacket
            run_id = getattr(run_context, "run_id", "local_run") if run_context else "local_run"
            edition_key = getattr(run_context, "edition_key", "default_edition") if run_context else "default_edition"
            context_packet = ContextPacket(
                run_id=str(run_id),
                edition_key=str(edition_key),
                micro_topic_id=request.micro_topic_id,
                theme_id=request.theme_id,
                query=request.query,
                current_content={"id": current_item.get("id"), "title": current_item.get("title"), "source": current_item.get("source")},
                retrieved_evidence=tuple(selected_chunks),
                event_context=event_context or {},
                entity_context=request.entity_context,
                source_context={"source": current_item.get("source"), "url": current_item.get("url")},
                ranking={"ranked_count": len(ranked_chunks), "components_present": bool(ranked_chunks)},
                diversity=diversity_diag,
                provenance={
                    "evidence_count": len(selected_chunks),
                    "evidence_ids": [c.get("id") for c in selected_chunks],
                },
                budget={"max_results": request.max_results, "max_context": request.max_context, **budget_trace},
                budget_trace=budget_trace,
            )

            scope_rejected_all = bool(scope is not None and before_scope and not selected_chunks)
            status = "OK" if selected_chunks else (
                IntelligenceStatus.NO_RELEVANT_CONTENT.value if scope_rejected_all else IntelligenceStatus.INSUFFICIENT_EVIDENCE.value
            )

            res = RetrievalResult(
                micro_topic=classification.get("micro_topic", ""),
                query=request.query,
                chunks=selected_chunks,
                status=status,
                retrieval_intent=request.retrieval_intent,
                retrieval_request=request.to_dict(),
                context_packet=context_packet.to_dict(),
                diagnostics={
                    "before_scope": before_scope,
                    "after_scope": len(scoped_candidates),
                    "rejected_scope": rejected_scope,
                    "scope_rejection_rate": round(rejected_scope / max(1, before_scope), 3),
                    "eligibility": eligibility_diag,
                    "diversity": diversity_diag,
                },
            )
            self.cache.set(cache_key, res.to_dict())
            return res
        except Exception as error:
            self.metrics["failures"] += 1
            empty_packet = ContextPacket(
                micro_topic_id=classification.get("micro_topic_id") or classification.get("micro_topic", "") if classification else "",
                query="",
            )
            return RetrievalResult(
                micro_topic=classification.get("micro_topic", "") if classification else "",
                query="",
                chunks=[],
                status=IntelligenceStatus.RETRIEVAL_FAILURE.value,
                context_packet=empty_packet.to_dict(),
                rejection_reason=str(error),
                diagnostics={
                    "before_scope": 0,
                    "after_scope": 0,
                    "rejected_scope": 0,
                    "error": str(error),
                },
            )


RAGManager = ProductionRAGManager

