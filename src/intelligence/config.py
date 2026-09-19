from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any

import yaml

from .validation import (
    validate_dimensions,
    validate_microtopic_matrix,
    validate_microtopic_profiles,
    validate_normalization_registry,
    validate_microtopics,
    validate_profile_templates,
    validate_sources,
    validate_taxonomy,
    validate_topics,
    validate_themes,
    validate_theme_specificity,
)
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


def _load_themes(config_dir: Path) -> list[dict[str, Any]]:
    registry_path = config_dir / "themes" / "registry.yaml"
    if registry_path.exists():
        registry = _read_yaml(registry_path)
        includes = registry.get("includes", [])
        themes_dir = config_dir / "themes"
        all_themes: list[dict[str, Any]] = []
        for inc in includes:
            inc_path = themes_dir / inc
            if inc_path.exists():
                file_data = _read_yaml(inc_path)
                if isinstance(file_data, dict):
                    all_themes.extend(file_data.get("themes", []))
                elif isinstance(file_data, list):
                    all_themes.extend(file_data)
        if all_themes:
            return all_themes
    themes_path = config_dir / "themes.yaml"
    if themes_path.exists():
        return _read_yaml(themes_path).get("themes", [])
    return []


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
    settings = _read_yaml(config_dir / "settings.yaml")
    themes = _load_themes(config_dir)
    themes = build_matrix_themes(matrix["records"], profile_templates, themes)
    validate_themes(themes, taxonomy, matrix)
    profile_mode = settings.get("intelligence", {}).get("profile_mode", "production")
    validate_microtopic_profiles(microtopics, taxonomy, matrix, themes, profile_templates, production=profile_mode == "production")
    validate_theme_specificity(themes)
    registry_path = config_dir / "source_registry.yaml"
    if registry_path.exists():
        registry = _read_yaml(registry_path).get("sources", [])
        configured = settings.setdefault("news", {}).setdefault("sources", [])
        existing = {source.get("id") for source in configured}
        configured.extend(source for source in registry if source.get("id") not in existing)
    validate_sources(settings.get("news", {}).get("sources", []), taxonomy)
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


def validate_runtime_production_config(root: Path) -> dict[str, Any]:
    """Fail-fast validation for all production-critical runtime configurations."""
    config_dir = root / "config"
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Provider configuration
    settings_file = config_dir / "settings.yaml"
    if not settings_file.is_file():
        errors.append("MISSING_SETTINGS_FILE: config/settings.yaml not found")
    else:
        settings = _read_yaml(settings_file)
        if not settings.get("intelligence"):
            errors.append("MISSING_PROVIDER_CONFIG: intelligence provider settings missing")

        budgets = settings.get("budgets", {})
        if not budgets:
            errors.append("INVALID_TOKEN_BUDGET: budgets configuration missing")
        elif any(v < 0 for v in budgets.values() if isinstance(v, (int, float))):
            errors.append("INVALID_TOKEN_BUDGET: negative budget limits configured")

        pipeline_cfg = settings.get("pipeline", {})
        timeout = pipeline_cfg.get("timeout_seconds", 30)
        if timeout <= 0:
            errors.append("INVALID_TIMEOUT: timeout_seconds must be positive")

        retry_count = pipeline_cfg.get("retry_count", 3)
        if retry_count < 0:
            errors.append("INVALID_RETRY_COUNT: retry_count cannot be negative")

        smtp_cfg = settings.get("smtp", {})
        if smtp_cfg.get("enabled"):
            if not smtp_cfg.get("host") or not smtp_cfg.get("port"):
                errors.append("INVALID_SMTP_CONFIGURATION: host or port missing for enabled SMTP")

    # 2. Source configuration
    source_file = config_dir / "source_registry.yaml"
    if not source_file.is_file():
        errors.append("MISSING_SOURCE_CONFIG: config/source_registry.yaml not found")
    else:
        sources = _read_yaml(source_file).get("sources", [])
        if not sources:
            errors.append("EMPTY_SOURCE_REGISTRY: no sources configured")
        sids = [s.get("id") for s in sources]
        if len(sids) != len(set(sids)):
            errors.append("DUPLICATE_SOURCE_IDS: duplicate source IDs found")

    # 3. Theme configuration
    themes = _load_themes(config_dir)
    mt_themes = [t for t in themes if t.get("micro_topic") not in {"any", "*", None}]
    if len(mt_themes) < 236:
        errors.append(f"INCOMPLETE_THEME_CONFIGURATION: expected 236 bespoke micro-topic themes, found {len(mt_themes)}")

    # 4. Persistence paths
    for p in ("data", "output"):
        target = root / p
        try:
            target.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            errors.append(f"INVALID_PERSISTENCE_PATH: cannot access {p}: {exc}")

    # 5. API credentials check (verify no placeholder/whitespace values when set)
    for env_var in ("GEMINI_API_KEY", "YOUTUBE_API_KEY", "NEWS_API_KEY"):
        val = os.environ.get(env_var, "")
        if val and (val.strip() in {"PLACEHOLDER", "YOUR_KEY_HERE", "NONE"} or " " in val):
            errors.append(f"INVALID_API_CREDENTIALS: {env_var} contains invalid placeholder or whitespace")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "checked_at": datetime.now(UTC).isoformat(),
    }
