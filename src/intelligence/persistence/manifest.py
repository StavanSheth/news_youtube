"""Authoritative RunManifest tracking complete pipeline execution lifecycle and provenance."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .atomic import atomic_write_json, read_json_safe


@dataclass
class RunManifest:
    """Canonical run manifest recording versions, parameters, counts, budgets, and status."""

    run_id: str
    edition_key: str
    started_at: str
    completed_at: str = ""
    status: str = "RUN_CREATED"
    versions: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    budgets: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def mark_completed(self, status: str = "COMPLETED") -> None:
        self.status = status
        self.completed_at = datetime.now(UTC).isoformat()

    def mark_failed(self, error: str | dict[str, Any]) -> None:
        self.status = "FAILED"
        self.completed_at = datetime.now(UTC).isoformat()
        if isinstance(error, dict):
            self.errors.append(error)
        else:
            self.errors.append({"message": str(error), "timestamp": self.completed_at})

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "edition_key": self.edition_key,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "versions": dict(self.versions),
            "counts": dict(self.counts),
            "budgets": dict(self.budgets),
            "metrics": dict(self.metrics),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "artifacts": dict(self.artifacts),
            "metadata": dict(self.metadata),
        }

    def save(self, path: Path | str) -> None:
        """Atomically persist manifest to path."""
        atomic_write_json(path, self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunManifest":
        return cls(
            run_id=str(data.get("run_id", "")),
            edition_key=str(data.get("edition_key", "")),
            started_at=str(data.get("started_at", "")),
            completed_at=str(data.get("completed_at", "")),
            status=str(data.get("status", "COMPLETED")),
            versions=dict(data.get("versions", {})),
            counts=dict(data.get("counts", {})),
            budgets=dict(data.get("budgets", {})),
            metrics=dict(data.get("metrics", {})),
            errors=list(data.get("errors", [])),
            warnings=list(data.get("warnings", [])),
            artifacts=dict(data.get("artifacts", {})),
            metadata=dict(data.get("metadata", {})),
        )

    @classmethod
    def load(cls, path: Path | str) -> "RunManifest" | None:
        data = read_json_safe(path)
        if not isinstance(data, dict):
            return None
        return cls.from_dict(data)
