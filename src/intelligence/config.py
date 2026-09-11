from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
import json

from .validation import validate_dimensions, validate_microtopic_matrix, validate_normalization_registry, validate_microtopics, validate_profile_templates, validate_sources, validate_taxonomy, validate_topics, validate_themes
from .contracts import VersionContract
from .profiles import build_matrix_themes


@dataclass(frozen=True)
class AppConfig:
    channels: list[dict[str, Any]]
    topics: list[dict[str, Any]]
    prompts: dict[str, str]
    settings: dict[str, Any]
    taxonomy: dict[str, Any]
    themes: list[dict[str, Any]]
    microtopics: dict[str, Any]
    microtopic_matrix: dict[str, Any]
    normalization_registry: dict[str, Any]
    dimensions: dict[str, Any]
    profile_templates: dict[str, Any]
    entities: list[dict[str, Any]]
    versions: VersionContract


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def load_config(root: Path) -> AppConfig:
    config_dir = root / "config"
    taxonomy = _read_yaml(config_dir / "taxonomy.yaml")
    topics = _read_yaml(config_dir / "topics.yaml").get("topics", [])
    validate_taxonomy(taxonomy)
    versions = VersionContract.from_mapping(_read_yaml(config_dir / "version.yaml"))
    if versions.taxonomy_version != str(taxonomy.get("version", "")):
        raise ValueError("version.yaml taxonomy_version must match taxonomy.yaml version")
    validate_topics(topics, taxonomy)
    microtopics = _read_yaml(config_dir / "microtopics.yaml")
    validate_microtopics(microtopics, taxonomy)
    matrix = _read_json(config_dir / "microtopic_matrix.json")
    validate_microtopic_matrix(matrix)
    normalization = _read_json(config_dir / "normalization_registry.json")
    validate_normalization_registry(normalization, matrix)
    dimensions = _read_json(config_dir / "dimensions.json")
    validate_dimensions(dimensions)
    profile_templates = _read_json(config_dir / "profile_templates.json")
    validate_profile_templates(matrix, profile_templates)
    themes = _read_yaml(config_dir / "themes.yaml").get("themes", [])
    themes = build_matrix_themes(matrix["records"], profile_templates, themes)
    validate_themes(themes, taxonomy, matrix)
    settings = _read_yaml(config_dir / "settings.yaml")
    registry_path = config_dir / "source_registry.yaml"
    if registry_path.exists():
        registry = _read_yaml(registry_path).get("sources", [])
        configured = settings.setdefault("news", {}).setdefault("sources", [])
        existing = {source.get("id") for source in configured}
        configured.extend(source for source in registry if source.get("id") not in existing)
    validate_sources(settings.get("news", {}).get("sources", []))
    return AppConfig(
        channels=_read_yaml(config_dir / "channels.yaml").get("channels", []),
        topics=topics,
        prompts=_read_yaml(config_dir / "prompts.yaml"),
        settings=settings,
        taxonomy=_read_yaml(config_dir / "taxonomy.yaml"),
        themes=themes,
        microtopics=microtopics,
        microtopic_matrix=matrix,
        normalization_registry=normalization,
        dimensions=dimensions,
        profile_templates=profile_templates,
        entities=_read_yaml(config_dir / "entities.yaml").get("entities", []),
        versions=versions,
    )
