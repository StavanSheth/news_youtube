from __future__ import annotations

from pathlib import Path

from .application.pipeline import run_pipeline
from .production import run as run_production  # noqa: F401


def run(root: Path, dry_run: bool = False) -> tuple[Path, Path]:
    """Compatibility facade delegating to authoritative application.pipeline.run_pipeline."""
    return run_pipeline(root, dry_run=dry_run)

