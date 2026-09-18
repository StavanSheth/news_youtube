"""RAG subsystem delivering bounded, verified evidence packets."""

from .corpus import EvidenceCorpus, RepositoryEvidenceCorpus
from .diversity import apply_diversity_filtering
from .eligibility import check_chunk_eligibility, filter_eligible_candidates
from .manager import ProductionRAGManager, RAGManager
from .packet import ContextPacket
from .query import RetrievalRequest, build_retrieval_request
from .ranking import rank_evidence_chunks

__all__ = [
    "EvidenceCorpus",
    "RepositoryEvidenceCorpus",
    "apply_diversity_filtering",
    "check_chunk_eligibility",
    "filter_eligible_candidates",
    "ProductionRAGManager",
    "RAGManager",
    "ContextPacket",
    "RetrievalRequest",
    "build_retrieval_request",
    "rank_evidence_chunks",
]
