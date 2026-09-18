"""Authoritative RAG Manager integrating corpus, eligibility, query, ranking, and diversity."""

from __future__ import annotations

from typing import Any

from .corpus import EvidenceCorpus, RepositoryEvidenceCorpus
from .diversity import apply_diversity_filtering
from .eligibility import filter_eligible_candidates
from .packet import ContextPacket
from .query import build_retrieval_request
from .ranking import rank_evidence_chunks
from ..evidence_scope import EvidenceScope
from ..statuses import IntelligenceStatus


class ProductionRAGManager:
    """Production-grade RAG orchestrator executing the complete Set E pipeline."""

    def __init__(
        self,
        settings: dict[str, Any],
        corpus: EvidenceCorpus | None = None,
    ) -> None:
        self.settings = settings
        self.corpus = corpus or RepositoryEvidenceCorpus(
            chunk_size=int(settings.get("retrieval_chunk_size", 1400)),
            chunk_overlap=int(settings.get("retrieval_chunk_overlap", 180)),
        )
        self.metrics: dict[str, Any] = {
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
        item: dict[str, Any],
        classification: dict[str, Any],
        theme: dict[str, Any],
        event_context: dict[str, Any] | None = None,
        scope: EvidenceScope | None = None,
        run_context: Any | None = None,
    ) -> dict[str, Any]:
        """Execute full RAG retrieval pipeline returning structured result and context packet."""
        self.metrics["retrievals"] += 1
        try:
            # Step 1: Ensure current item is indexed in corpus
            current_chunks = self.index_item(item)
            before_scope = len(current_chunks)

            # Step 2: Build authoritative RetrievalRequest
            budget_config = {
                "max_rag_items": self.settings.get("retrieval_top_k", 4),
                "max_context_chars": self.settings.get("max_retrieved_context_chars", 12000),
            }
            cutoff = getattr(run_context, "publication_cutoff_utc", None) if run_context else None
            request = build_retrieval_request(
                micro_topic=classification.get("micro_topic_id") or classification.get("micro_topic", ""),
                theme=theme,
                classification=classification,
                event_context=event_context,
                cutoff=cutoff,
                budget=budget_config,
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

            # Step 5: Hard eligibility check before ranking
            eligible_chunks, eligibility_diag = filter_eligible_candidates(
                scoped_candidates,
                request,
                publication_cutoff=cutoff,
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
                current_content={"id": item.get("id"), "title": item.get("title"), "source": item.get("source")},
                retrieved_evidence=tuple(selected_chunks),
                event_context=event_context or {},
                entity_context=request.entity_context,
                source_context={"source": item.get("source"), "url": item.get("url")},
                ranking={"ranked_count": len(ranked_chunks), "components_present": bool(ranked_chunks)},
                diversity=diversity_diag,
                provenance={
                    "evidence_count": len(selected_chunks),
                    "evidence_ids": [c.get("id") for c in selected_chunks],
                },
                budget={"max_results": request.max_results, "max_context": request.max_context},
            )

            scope_rejected_all = bool(scope is not None and before_scope and not selected_chunks)
            status = "OK" if selected_chunks else (
                IntelligenceStatus.NO_RELEVANT_CONTENT.value if scope_rejected_all else IntelligenceStatus.INSUFFICIENT_EVIDENCE.value
            )

            return {
                "micro_topic": classification.get("micro_topic", ""),
                "query": request.query,
                "chunks": selected_chunks,
                "status": status,
                "retrieval_intent": request.retrieval_intent,
                "retrieval_request": request.to_dict(),
                "context_packet": context_packet.to_dict(),
                "diagnostics": {
                    "before_scope": before_scope,
                    "after_scope": len(scoped_candidates),
                    "rejected_scope": rejected_scope,
                    "scope_rejection_rate": round(rejected_scope / max(1, before_scope), 3),
                    "eligibility": eligibility_diag,
                    "diversity": diversity_diag,
                },
            }
        except Exception as error:
            self.metrics["failures"] += 1
            return {
                "micro_topic": classification.get("micro_topic", ""),
                "query": "",
                "chunks": [],
                "status": IntelligenceStatus.RETRIEVAL_FAILURE.value,
                "error_type": type(error).__name__,
            }
