"""Tests for theme event extraction configuration."""

from __future__ import annotations

from pathlib import Path
from intelligence.config import load_config

ROOT = Path(__file__).resolve().parent.parent.parent


def test_all_bespoke_themes_have_event_extraction_rules():
    config = load_config(ROOT)
    exact_themes = [
        t for t in config.themes
        if t.get("id") != "domain-fallback" and t.get("micro_topic") not in {None, "any", "*"}
    ]
    for theme in exact_themes:
        events = theme.get("event_extraction") or theme.get("event_fields") or {}
        assert bool(events), f"Theme {theme.get('id')} missing event extraction configuration"
        event_types = events.get("event_types", [])
        assert len(event_types) >= 1, f"Theme {theme.get('id')} missing event_types"
