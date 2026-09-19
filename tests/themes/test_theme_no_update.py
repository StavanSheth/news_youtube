"""Tests for theme no-update policy completeness and explanatory quality."""

from __future__ import annotations

from pathlib import Path
from intelligence.config import load_config

ROOT = Path(__file__).resolve().parent.parent.parent


def test_all_bespoke_themes_have_no_update_policy():
    config = load_config(ROOT)
    exact_themes = [
        t for t in config.themes
        if t.get("id") != "domain-fallback" and t.get("micro_topic") not in {None, "any", "*"}
    ]
    for theme in exact_themes:
        policy = theme.get("no_update_policy", {})
        assert bool(policy), f"Theme {theme.get('id')} missing no_update_policy"
        assert "NO_MAJOR_UPDATE" in policy, f"Theme {theme.get('id')} missing NO_MAJOR_UPDATE"
        assert "INSUFFICIENT_EVIDENCE" in policy, f"Theme {theme.get('id')} missing INSUFFICIENT_EVIDENCE"
        assert len(policy["NO_MAJOR_UPDATE"]) > 20, f"Theme {theme.get('id')} NO_MAJOR_UPDATE message too terse"
