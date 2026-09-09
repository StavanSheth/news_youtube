from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .validation import validate_taxonomy, validate_topics


@dataclass(frozen=True)
class AppConfig:
    channels: list[dict[str, Any]]
    topics: list[dict[str, Any]]
    prompts: dict[str, str]
    settings: dict[str, Any]
    taxonomy: dict[str, Any]
    themes: list[dict[str, Any]]


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_config(root: Path) -> AppConfig:
    config_dir = root / "config"
    taxonomy = _read_yaml(config_dir / "taxonomy.yaml")
    topics = _read_yaml(config_dir / "topics.yaml").get("topics", [])
    validate_taxonomy(taxonomy)
    validate_topics(topics, taxonomy)
    return AppConfig(
        channels=_read_yaml(config_dir / "channels.yaml").get("channels", []),
        topics=topics,
        prompts=_read_yaml(config_dir / "prompts.yaml"),
        settings=_read_yaml(config_dir / "settings.yaml"),
        taxonomy=_read_yaml(config_dir / "taxonomy.yaml"),
        themes=_read_yaml(config_dir / "themes.yaml").get("themes", []),
    )
