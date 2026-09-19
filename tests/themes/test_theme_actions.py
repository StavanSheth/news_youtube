"""Tests for theme action rules (monitor, investigate)."""

from __future__ import annotations

from pathlib import Path
from intelligence.config import load_config

ROOT = Path(__file__).resolve().parent.parent.parent


def test_all_bespoke_themes_have_action_rules():
    config = load_config(ROOT)
    exact_themes = [
        t for t in config.themes
        if t.get("id") != "domain-fallback" and t.get("micro_topic") not in {None, "any", "*"}
    ]
    for theme in exact_themes:
        actions = theme.get("action_rules", {})
        assert bool(actions), f"Theme {theme.get('id')} missing action_rules"
        assert "monitor" in actions or "investigate" in actions
        mon = actions.get("monitor", [])
        assert len(mon) >= 1, f"Theme {theme.get('id')} missing monitor actions"
