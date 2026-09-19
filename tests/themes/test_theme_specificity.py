"""Tests for theme specificity, genericness rejection, and lexical distinctness."""

from __future__ import annotations

from pathlib import Path
from intelligence.config import load_config
from intelligence.themes import (
    is_generic_theme,
    theme_fingerprint,
    theme_specificity_score,
)

ROOT = Path(__file__).resolve().parent.parent.parent


def test_no_generic_themes_configured():
    config = load_config(ROOT)
    exact_themes = [
        t for t in config.themes
        if t.get("id") != "domain-fallback" and t.get("micro_topic") not in {None, "any", "*"}
    ]
    for theme in exact_themes:
        assert not is_generic_theme(theme), f"Theme {theme.get('id')} flagged as generic template"


def test_theme_specificity_scores_meet_threshold():
    config = load_config(ROOT)
    exact_themes = [
        t for t in config.themes
        if t.get("id") != "domain-fallback" and t.get("micro_topic") not in {None, "any", "*"}
    ]
    for theme in exact_themes:
        score = theme_specificity_score(theme)
        assert score >= 0.55, f"Theme {theme.get('id')} specificity score {score} < 0.55"


def test_unique_theme_fingerprints():
    config = load_config(ROOT)
    exact_themes = [
        t for t in config.themes
        if t.get("id") != "domain-fallback" and t.get("micro_topic") not in {None, "any", "*"}
    ]
    seen = {}
    for theme in exact_themes:
        fp = theme_fingerprint(theme)
        assert fp not in seen, f"Duplicate fingerprint between {theme.get('id')} and {seen[fp]}"
        seen[fp] = theme.get("id")
