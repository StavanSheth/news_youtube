"""Authoritative evidence domain models, chunking strategies, and lifecycle."""

from __future__ import annotations

from .chunking import (
    CharacterChunker,
    Chunk,
    ChunkingStrategy,
    deterministic_chunks,
    semantic_chunks,
)
from .models import Evidence

__all__ = [
    "CharacterChunker",
    "Chunk",
    "ChunkingStrategy",
    "Evidence",
    "deterministic_chunks",
    "semantic_chunks",
]
