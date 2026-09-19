"""Tests for theme entity extraction rules."""

from __future__ import annotations

from pathlib import Path
from intelligence.config import load_config

ROOT = Path(__file__).resolve().parent.parent.parent


def test_all_bespoke_themes_have_entity_extraction_rules():
    config = load_config(ROOT)
    exact_themes = [
        t for t in config.themes
        if t.get("id") != "domain-fallback" and t.get("micro_topic") not in {None, "any", "*"}
    ]
    for theme in exact_themes:
        entities = theme.get("entity_extraction") or theme.get("entity_fields") or {}
        assert bool(entities), f"Theme {theme.get('id')} missing entity extraction configuration"
        assert "required" in entities or "optional" in entities
        required = entities.get("required", [])
        assert len(required) >= 1, f"Theme {theme.get('id')} missing required entity fields"
