"""Application layer: canonical pipeline, orchestrator, edition runner, and execution lifecycle."""

from __future__ import annotations

from .edition_runner import EditionRunner, resolve_edition_context
from .item_processor import ItemProcessor, ProcessedItem, SourceItem
from .lifecycle import RunLifecycleStage, RunSummary
from .orchestrator import ApplicationOrchestrator
from .pipeline import CanonicalPipeline, eligible_for_edition, render_newsletter, run_pipeline

__all__ = [
    "ApplicationOrchestrator",
    "CanonicalPipeline",
    "EditionRunner",
    "ItemProcessor",
    "ProcessedItem",
    "RunLifecycleStage",
    "RunSummary",
    "SourceItem",
    "eligible_for_edition",
    "render_newsletter",
    "resolve_edition_context",
    "run_pipeline",
]
