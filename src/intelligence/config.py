from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class AppConfig:
    channels: list[dict[str, Any]]
    topics: list[dict[str, Any]]
    prompts: dict[str, str]
    settings: dict[str, Any]


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_config(root: Path) -> AppConfig:
    config_dir = root / "config"
    return AppConfig(
        channels=_read_yaml(config_dir / "channels.yaml").get("channels", []),
        topics=_read_yaml(config_dir / "topics.yaml").get("topics", []),
        prompts=_read_yaml(config_dir / "prompts.yaml"),
        settings=_read_yaml(config_dir / "settings.yaml"),
    )
