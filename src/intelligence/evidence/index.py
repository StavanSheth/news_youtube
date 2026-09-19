"""Evidence index re-export and index protocol."""

from __future__ import annotations

from ..rag.index import EvidenceIndex, compute_dense_vector, cosine_similarity, tokenize

__all__ = ["EvidenceIndex", "compute_dense_vector", "cosine_similarity", "tokenize"]
