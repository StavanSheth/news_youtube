"""Authoritative repository persistence package providing paths, atomic IO, manifests, and recovery."""

from __future__ import annotations

from .atomic import atomic_write_json, atomic_write_text, read_json_safe
from .manifest import RunManifest
from .paths import PersistencePaths
from .recovery import is_run_resumable, load_checkpoint, save_checkpoint

__all__ = [
    "PersistencePaths",
    "RunManifest",
    "atomic_write_json",
    "atomic_write_text",
    "is_run_resumable",
    "load_checkpoint",
    "read_json_safe",
    "save_checkpoint",
]
