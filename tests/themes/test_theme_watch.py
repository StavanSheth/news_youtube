"""Tests for theme watch rules and forward-looking indicators."""

from __future__ import annotations

from pathlib import Path
from intelligence.config import load_config

ROOT = Path(__file__).resolve().parent.parent.parent


def test_all_bespoke_themes_have_watch_rules():
    config = load_config(ROOT)
    exact_themes = [
        t for t in config.themes
        if t.get("id") != "domain-fallback" and t.get("micro_topic") not in {None, "any", "*"}
    ]
    for theme in exact_themes:
        watch = theme.get("watch_rules", {})
        assert bool(watch), f"Theme {theme.get('id')} missing watch_rules"
        mon = watch.get("monitor", [])
        assert len(mon) >= 1, f"Theme {theme.get('id')} missing watch_rules.monitor"
