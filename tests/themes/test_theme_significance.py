"""Tests for theme significance rules."""

from __future__ import annotations

from pathlib import Path
from intelligence.config import load_config

ROOT = Path(__file__).resolve().parent.parent.parent


def test_all_bespoke_themes_have_significance_rules():
    config = load_config(ROOT)
    exact_themes = [
        t for t in config.themes
        if t.get("id") != "domain-fallback" and t.get("micro_topic") not in {None, "any", "*"}
    ]
    for theme in exact_themes:
        sig = theme.get("significance_rules", {})
        assert bool(sig), f"Theme {theme.get('id')} missing significance rules"
        assert len(sig.get("significant_if", [])) >= 1, f"Theme {theme.get('id')} missing significant_if"
        assert len(sig.get("insignificant_if", [])) >= 1, f"Theme {theme.get('id')} missing insignificant_if"
