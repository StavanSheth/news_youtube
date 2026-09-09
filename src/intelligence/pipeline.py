from __future__ import annotations

from pathlib import Path

from .production import run as run_production


def run(root: Path, dry_run: bool = False) -> tuple[Path, Path]:
    """Compatibility wrapper: production.py is the sole authoritative path."""
    return run_production(root, dry_run=dry_run)
