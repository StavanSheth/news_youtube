"""Authoritative infrastructure configuration loader."""

from __future__ import annotations

from pathlib import Path

import yaml

from ..config import AppConfig, load_config as base_load_config


def load_application_config(root: Path) -> AppConfig:
    """Load and merge modular YAML configuration files."""
    app_config = base_load_config(root)
    config_dir = root / "config"

    # Merge modular config files if present
    settings = dict(app_config.settings)

    models_path = config_dir / "models.yaml"
    if models_path.exists():
        with models_path.open(encoding="utf-8") as f:
            models_data = yaml.safe_load(f) or {}
            settings.setdefault("gemini", {}).update(models_data.get("analysis", {}))
            settings["models"] = models_data

    budgets_path = config_dir / "budgets.yaml"
    if budgets_path.exists():
        with budgets_path.open(encoding="utf-8") as f:
            budgets_data = yaml.safe_load(f) or {}
            settings.setdefault("budgets", {}).update(budgets_data.get("global", {}))
            settings["budgets_config"] = budgets_data

    retrieval_path = config_dir / "retrieval.yaml"
    if retrieval_path.exists():
        with retrieval_path.open(encoding="utf-8") as f:
            retrieval_data = yaml.safe_load(f) or {}
            settings.setdefault("retrieval", {}).update(retrieval_data.get("retrieval", {}))

    application_path = config_dir / "application.yaml"
    if application_path.exists():
        with application_path.open(encoding="utf-8") as f:
            app_data = yaml.safe_load(f) or {}
            for key, val in app_data.items():
                if isinstance(val, dict) and isinstance(settings.get(key), dict):
                    settings[key].update(val)
                else:
                    settings.setdefault(key, val)

    # Return new AppConfig with merged settings
    return AppConfig(
        channels=app_config.channels,
        topics=app_config.topics,
        prompts=app_config.prompts,
        settings=settings,
        taxonomy=app_config.taxonomy,
        themes=app_config.themes,
        microtopics=app_config.microtopics,
        microtopic_matrix=app_config.microtopic_matrix,
        normalization_registry=app_config.normalization_registry,
        dimensions=app_config.dimensions,
        profile_templates=app_config.profile_templates,
        entities=app_config.entities,
        versions=app_config.versions,
    )
