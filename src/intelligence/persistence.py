"""Central repository-native persistence path contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .contracts import EditionContext, RunContext


def _safe_segment(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "root"


@dataclass(frozen=True)
class PersistencePaths:
    root: Path

    @classmethod
    def for_root(cls, root: Path) -> "PersistencePaths":
        return cls(root.resolve())

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def output(self) -> Path:
        return self.root / "output"

    @property
    def archive(self) -> Path:
        return self.root / "archive"

    def data_file(self, name: str) -> Path:
        return self.data / name

    def edition_dir(self, edition: EditionContext | str) -> Path:
        key = edition if isinstance(edition, str) else edition.edition_key
        return self.output / _safe_segment(key)

    def run_dir(self, run: RunContext) -> Path:
        return self.edition_dir(run.edition_key) / _safe_segment(run.run_id)

    def archive_run_dir(self, edition: EditionContext, run: RunContext) -> Path:
        return self.archive / "runs" / _safe_segment(edition.edition_key) / _safe_segment(run.run_id)
