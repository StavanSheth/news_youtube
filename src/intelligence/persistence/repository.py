"""Authoritative repository interface and implementation for atomic domain persistence."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Protocol

from .atomic import atomic_write_json, read_json_safe
from .manifest import RunManifest
from .paths import PersistencePaths


def _safe_key(val: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", val).strip("._") or "unnamed"


class RepositoryProtocol(Protocol):
    """Authoritative protocol for all persistence operations."""

    def save_source(self, source_id: str, payload: dict[str, Any]) -> Path: ...
    def save_content(self, content_id: str, payload: dict[str, Any]) -> Path: ...
    def save_evidence(self, evidence_id: str, payload: dict[str, Any]) -> Path: ...
    def save_event(self, event_id: str, payload: dict[str, Any]) -> Path: ...
    def save_entity(self, entity_id: str, payload: dict[str, Any]) -> Path: ...
    def save_run(self, run_id: str, manifest: RunManifest | dict[str, Any]) -> Path: ...
    def save_analysis(self, analysis_id: str, payload: dict[str, Any]) -> Path: ...
    def save_budget_snapshot(self, run_id: str, budget_data: dict[str, Any]) -> Path: ...
    def save_delivery(self, delivery_id: str, payload: dict[str, Any]) -> Path: ...
    def save_source_health(self, source_id: str, record: dict[str, Any]) -> Path: ...
    def get_source_health(self, source_id: str) -> dict[str, Any] | None: ...
    def save_all_source_health(self, records: dict[str, dict[str, Any]]) -> None: ...
    def get_all_source_health(self) -> dict[str, dict[str, Any]]: ...


class ProductionRepository(RepositoryProtocol):
    """Authoritative repository enforcing atomic writes across the standard data tree."""

    def __init__(self, paths: PersistencePaths) -> None:
        self.paths = paths
        self.paths.ensure()

    @property
    def raw_dir(self) -> Path:
        return self.paths.raw

    @property
    def normalized_dir(self) -> Path:
        return self.paths.normalized

    @property
    def rag_dir(self) -> Path:
        return self.paths.rag

    @property
    def events_dir(self) -> Path:
        return self.paths.events

    @property
    def entities_dir(self) -> Path:
        return self.paths.entities

    @property
    def state_dir(self) -> Path:
        return self.paths.state

    @property
    def runs_dir(self) -> Path:
        return self.paths.runs

    @property
    def archive_dir(self) -> Path:
        return self.paths.archive

    def save_source(self, source_id: str, payload: dict[str, Any]) -> Path:
        target = self.raw_dir / f"{_safe_key(source_id)}.json"
        atomic_write_json(target, payload)
        return target

    def save_content(self, content_id: str, payload: dict[str, Any]) -> Path:
        target = self.normalized_dir / f"{_safe_key(content_id)}.json"
        atomic_write_json(target, payload)
        return target

    def save_evidence(self, evidence_id: str, payload: dict[str, Any]) -> Path:
        target = self.rag_dir / f"{_safe_key(evidence_id)}.json"
        atomic_write_json(target, payload)
        return target

    def save_event(self, event_id: str, payload: dict[str, Any]) -> Path:
        target = self.events_dir / f"{_safe_key(event_id)}.json"
        atomic_write_json(target, payload)
        return target

    def save_entity(self, entity_id: str, payload: dict[str, Any]) -> Path:
        target = self.entities_dir / f"{_safe_key(entity_id)}.json"
        atomic_write_json(target, payload)
        return target

    def save_run(self, run_id: str, manifest: RunManifest | dict[str, Any]) -> Path:
        run_folder = self.runs_dir / _safe_key(run_id)
        run_folder.mkdir(parents=True, exist_ok=True)
        target = run_folder / "run_manifest.json"
        payload = manifest.to_dict() if isinstance(manifest, RunManifest) else manifest
        atomic_write_json(target, payload)
        return target

    def save_analysis(self, analysis_id: str, payload: dict[str, Any]) -> Path:
        analysis_folder = self.state_dir / "analyses"
        analysis_folder.mkdir(parents=True, exist_ok=True)
        target = analysis_folder / f"{_safe_key(analysis_id)}.json"
        atomic_write_json(target, payload)
        return target

    @property
    def source_health_dir(self) -> Path:
        return self.paths.source_health_dir

    def save_budget_snapshot(self, run_id: str, budget_data: dict[str, Any]) -> Path:
        run_folder = self.runs_dir / _safe_key(run_id)
        run_folder.mkdir(parents=True, exist_ok=True)
        target = run_folder / "budget_snapshot.json"
        atomic_write_json(target, budget_data)
        return target

    def save_delivery(self, delivery_id: str, payload: dict[str, Any]) -> Path:
        delivery_folder = self.archive_dir / "deliveries"
        delivery_folder.mkdir(parents=True, exist_ok=True)
        target = delivery_folder / f"{_safe_key(delivery_id)}.json"
        atomic_write_json(target, payload)
        return target

    def get_content(self, content_id: str) -> dict[str, Any] | None:
        target = self.normalized_dir / f"{_safe_key(content_id)}.json"
        return read_json_safe(target)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        target = self.runs_dir / _safe_key(run_id) / "run_manifest.json"
        return read_json_safe(target)

    def save_source_health(self, source_id: str, record: dict[str, Any]) -> Path:
        self.source_health_dir.mkdir(parents=True, exist_ok=True)
        target = self.source_health_dir / f"{_safe_key(source_id)}.json"
        atomic_write_json(target, record)
        return target

    def get_source_health(self, source_id: str) -> dict[str, Any] | None:
        target = self.source_health_dir / f"{_safe_key(source_id)}.json"
        return read_json_safe(target)

    def save_all_source_health(self, records: dict[str, dict[str, Any]]) -> None:
        for source_id, record in records.items():
            self.save_source_health(source_id, record)

    def get_all_source_health(self) -> dict[str, dict[str, Any]]:
        if not self.source_health_dir.is_dir():
            return {}
        result: dict[str, dict[str, Any]] = {}
        for f in self.source_health_dir.glob("*.json"):
            data = read_json_safe(f)
            if isinstance(data, dict) and "source_id" in data:
                result[str(data["source_id"])] = data
        return result
