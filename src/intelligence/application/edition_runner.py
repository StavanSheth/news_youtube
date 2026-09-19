"""Authoritative EditionRunner managing edition lifecycle, context resolution, and run summaries."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from ..contracts import EditionContext, EditionType, RunContext, build_edition_context
from ..infrastructure.clock import now_utc
from ..persistence import PersistencePaths, ProductionRepository
from .lifecycle import RunLifecycleStage, RunSummary


def resolve_edition_context(
    settings: dict[str, Any],
    started_at: datetime,
    versions: Any,
) -> tuple[EditionContext, RunContext]:
    """Resolve authoritative edition and run contexts with timezone and cutoff."""
    edition_config = settings.get("edition", {})
    timezone = edition_config.get(
        "timezone", settings.get("pipeline", {}).get("timezone", "Asia/Kolkata")
    )
    local_date = started_at.astimezone(ZoneInfo(timezone)).date()
    cutoff_value = edition_config.get("publication_cutoff_local", "23:59:59")
    cutoff = time.fromisoformat(cutoff_value) if isinstance(cutoff_value, str) else cutoff_value

    edition = build_edition_context(
        local_date,
        EditionType(str(edition_config.get("type", "NIGHT")).upper()),
        timezone,
        cutoff,
        versions,
    )
    run = RunContext.create(edition, started_at)
    return replace(edition, run_id=run.run_id), run


class EditionRunner:
    """Authoritative lifecycle manager for edition runs, context resolution, and execution summaries."""

    def __init__(
        self,
        settings: dict[str, Any],
        paths: PersistencePaths,
        repository: ProductionRepository | None = None,
        versions: Any | None = None,
    ) -> None:
        self.settings = dict(settings)
        self.paths = paths
        self.repository = repository or ProductionRepository(paths)
        self.versions = versions
        self.edition_context: EditionContext | None = None
        self.run_context: RunContext | None = None
        self.summary: RunSummary | None = None

    def start(self, started_at: datetime | None = None) -> tuple[EditionContext, RunContext]:
        """Initialize edition lifecycle, resolve contexts, and create run summary."""
        started = started_at or now_utc()
        self.edition_context, self.run_context = resolve_edition_context(
            self.settings, started, self.versions
        )
        self.summary = RunSummary(
            run_id=self.run_context.run_id,
            edition_id=self.edition_context.edition_key,
            started_at=started.isoformat(),
            status=RunLifecycleStage.INITIALIZING.value,
            config_version=getattr(self.versions, "config_version", "1.0.0") if self.versions else "1.0.0",
            taxonomy_version=getattr(self.versions, "taxonomy_version", "1.0.0") if self.versions else "1.0.0",
            prompt_version=getattr(self.versions, "prompt_version", "1.0.0") if self.versions else "1.0.0",
            pipeline_version=getattr(self.versions, "pipeline_version", "2.0.0") if self.versions else "2.0.0",
        )
        return self.edition_context, self.run_context

    def finalize(
        self,
        status: str = RunLifecycleStage.COMPLETED.value,
        counts: dict[str, int] | None = None,
        budgets: dict[str, Any] | None = None,
    ) -> RunSummary:
        """Finalize the edition run, persist summary, and return completed record."""
        if not self.summary or not self.run_context:
            raise RuntimeError("Cannot finalize an edition run that has not been started.")

        self.summary.completed_at = now_utc().isoformat()
        self.summary.status = status
        if counts:
            self.summary.counts.update(counts)
        if budgets:
            self.summary.budget_usage.update(budgets)

        self.repository.save_run(self.run_context.run_id, self.summary.to_dict())
        return self.summary

    def fail(self, error: Exception | str) -> RunSummary:
        """Record an execution failure, update status to FAILED, and persist summary."""
        if not self.summary or not self.run_context:
            raise RuntimeError("Cannot fail an edition run that has not been started.")

        self.summary.completed_at = now_utc().isoformat()
        self.summary.mark_failed(str(error))
        self.repository.save_run(self.run_context.run_id, self.summary.to_dict())
        return self.summary
