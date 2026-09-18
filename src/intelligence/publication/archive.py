"""Durable repository-native archival for newsletter and intelligence runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def archive_edition_run(
    archive_dir: Path,
    edition_key: str,
    run_id: str,
    artifacts: dict[str, str | dict[str, Any]],
) -> Path:
    """Persist run artifacts to a deterministic directory structure."""
    safe_key = edition_key.replace("|", "_").replace(":", "_").replace("/", "_")
    target_dir = archive_dir / safe_key / f"run-{run_id}"
    target_dir.mkdir(parents=True, exist_ok=True)

    for filename, content in artifacts.items():
        file_path = target_dir / filename
        if isinstance(content, (dict, list)):
            file_path.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            file_path.write_text(str(content), encoding="utf-8")

    return target_dir
