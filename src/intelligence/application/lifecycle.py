"""Explicit run lifecycle stages and typed run summary contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RunLifecycleStage(StrEnum):
    """Authoritative 16-stage pipeline execution lifecycle."""

    CREATED = "CREATED"
    INITIALIZING = "INITIALIZING"
    COLLECTING = "COLLECTING"
    NORMALIZING = "NORMALIZING"
    FILTERING = "FILTERING"
    DEDUPLICATING = "DEDUPLICATING"
    CLASSIFYING = "CLASSIFYING"
    RETRIEVING = "RETRIEVING"
    ANALYZING = "ANALYZING"
    VALIDATING = "VALIDATING"
    ENRICHING = "ENRICHING"
    ASSEMBLING = "ASSEMBLING"
    RENDERING = "RENDERING"
    DELIVERING = "DELIVERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


@dataclass
class RunSummary:
    """Canonical run summary recording execution lifecycle, versioning, counts, and budgets."""

    run_id: str
    edition_id: str
    started_at: str
    completed_at: str = ""
    status: str = RunLifecycleStage.CREATED.value
    config_version: str = "1.0.0"
    taxonomy_version: str = "1.0.0"
    prompt_version: str = "1.0.0"
    pipeline_version: str = "2.0.0"
    counts: dict[str, int] = field(default_factory=dict)
    budget_usage: dict[str, Any] = field(default_factory=dict)
    failure_summary: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def mark_completed(self, status: str = RunLifecycleStage.COMPLETED.value) -> None:
        self.status = status

    def mark_failed(self, error: str | dict[str, Any]) -> None:
        self.status = RunLifecycleStage.FAILED.value
        if isinstance(error, dict):
            self.failure_summary.append(error)
        else:
            self.failure_summary.append({"error": str(error)})

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "edition_id": self.edition_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "config_version": self.config_version,
            "taxonomy_version": self.taxonomy_version,
            "prompt_version": self.prompt_version,
            "pipeline_version": self.pipeline_version,
            "counts": dict(self.counts),
            "budget_usage": dict(self.budget_usage),
            "failure_summary": list(self.failure_summary),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunSummary":
        return cls(
            run_id=str(data.get("run_id", "")),
            edition_id=str(data.get("edition_id", "")),
            started_at=str(data.get("started_at", "")),
            completed_at=str(data.get("completed_at", "")),
            status=str(data.get("status", RunLifecycleStage.CREATED.value)),
            config_version=str(data.get("config_version", "1.0.0")),
            taxonomy_version=str(data.get("taxonomy_version", "1.0.0")),
            prompt_version=str(data.get("prompt_version", "1.0.0")),
            pipeline_version=str(data.get("pipeline_version", "2.0.0")),
            counts=dict(data.get("counts", {})),
            budget_usage=dict(data.get("budget_usage", {})),
            failure_summary=list(data.get("failure_summary", [])),
            metadata=dict(data.get("metadata", {})),
        )
