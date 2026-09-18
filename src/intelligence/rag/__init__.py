"""RAG subsystem delivering bounded, verified evidence packets."""

from __future__ import annotations

from .corpus import EvidenceCorpus, RepositoryEvidenceCorpus, deterministic_chunks, semantic_chunks
from .diversity import apply_diversity_filtering
from .eligibility import check_chunk_eligibility, filter_eligible_candidates
from .fusion import reciprocal_rank_fusion
from .index import EvidenceIndex
from .manager import ProductionRAGManager, RAGManager
from .packet import ContextPacket
from .provenance import extract_provenance_chain, validate_evidence_provenance
from .query import RetrievalRequest, build_retrieval_request
from .ranking import rank_evidence_chunks
from .retrieval import HybridRetriever, LocalCrossEncoderReranker, NoOpReranker, Reranker

__all__ = [
    "ContextPacket",
    "EvidenceCorpus",
    "EvidenceIndex",
    "HybridRetriever",
    "LocalCrossEncoderReranker",
    "NoOpReranker",
    "ProductionRAGManager",
    "RAGManager",
    "RepositoryEvidenceCorpus",
    "Reranker",
    "RetrievalRequest",
    "apply_diversity_filtering",
    "build_retrieval_request",
    "check_chunk_eligibility",
    "deterministic_chunks",
    "extract_provenance_chain",
    "filter_eligible_candidates",
    "rank_evidence_chunks",
    "reciprocal_rank_fusion",
    "semantic_chunks",
    "validate_evidence_provenance",
]
