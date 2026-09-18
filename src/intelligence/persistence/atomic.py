"""Atomic file write operations ensuring crash-consistent updates without partial reads."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any


def atomic_write_text(path: Path | str, content: str, encoding: str = "utf-8") -> None:
    """Atomically write text content to path via temporary file and atomic replace."""
    target_path = Path(path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_file = tempfile.NamedTemporaryFile(
        dir=target_path.parent,
        delete=False,
        prefix=f".{target_path.name}.tmp_",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_file.name)
    try:
        tmp_file.write(content.encode(encoding))
        tmp_file.flush()
        os.fsync(tmp_file.fileno())
        tmp_file.close()

        # Atomic rename replacing destination atomically
        os.replace(tmp_path, target_path)
    except Exception:
        tmp_file.close()
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def atomic_write_json(path: Path | str, data: Any, indent: int = 2) -> None:
    """Atomically write JSON data to path formatted with indentation."""
    content = json.dumps(data, indent=indent, ensure_ascii=False)
    atomic_write_text(path, content)


def read_json_safe(path: Path | str) -> Any | None:
    """Read and parse JSON from file, returning None on missing or corrupt files."""
    target = Path(path)
    if not target.is_file():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
