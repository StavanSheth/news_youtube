"""State recovery and checkpointing to support crash-resilient run resumption."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .atomic import atomic_write_json, read_json_safe
from .manifest import RunManifest


def is_run_resumable(run_dir: Path | str) -> bool:
    """Check if a run directory contains an incomplete but resumable manifest."""
    manifest_path = Path(run_dir) / "run_manifest.json"
    manifest = RunManifest.load(manifest_path)
    if not manifest:
        return False
    return manifest.status in {"RUN_CREATED", "RUNNING", "PARTIAL", "FAILED"}


def save_checkpoint(run_dir: Path | str, stage_name: str, payload: Any) -> Path:
    """Atomically persist a stage checkpoint within the run directory."""
    checkpoints_dir = Path(run_dir) / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_file = checkpoints_dir / f"{stage_name}.json"
    atomic_write_json(checkpoint_file, payload)
    return checkpoint_file


def load_checkpoint(run_dir: Path | str, stage_name: str) -> Any | None:
    """Load a previously persisted stage checkpoint if present."""
    checkpoint_file = Path(run_dir) / "checkpoints" / f"{stage_name}.json"
    return read_json_safe(checkpoint_file)
