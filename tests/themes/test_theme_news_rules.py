"""Tests for theme stream_rules.news requirements."""

from __future__ import annotations

from pathlib import Path
from intelligence.config import load_config

ROOT = Path(__file__).resolve().parent.parent.parent


def test_all_bespoke_themes_have_news_stream_rules():
    config = load_config(ROOT)
    exact_themes = [
        t for t in config.themes
        if t.get("id") != "domain-fallback" and t.get("micro_topic") not in {None, "any", "*"}
    ]
    for theme in exact_themes:
        stream_rules = theme.get("stream_rules") or theme.get("content_streams") or {}
        news = stream_rules.get("news")
        assert bool(news), f"Theme {theme.get('id')} missing stream_rules.news"
        assert "freshness" in news, f"Theme {theme.get('id')} missing news.freshness"
        assert "focus" in news, f"Theme {theme.get('id')} missing news.focus"
        assert len(news["focus"]) >= 1
