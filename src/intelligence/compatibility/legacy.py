"""Legacy compatibility re-exports to ensure older scripts and consumers continue working."""

from __future__ import annotations

from ..ai import DryRunProvider, GeminiProvider
from ..application.orchestrator import ApplicationOrchestrator
from ..contracts import VersionContract
from ..rag.manager import ProductionRAGManager, RAGManager

__all__ = [
    "ApplicationOrchestrator",
    "DryRunProvider",
    "GeminiProvider",
    "ProductionRAGManager",
    "RAGManager",
    "VersionContract",
]
