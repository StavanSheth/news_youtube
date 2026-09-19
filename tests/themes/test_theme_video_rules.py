"""Tests for theme stream_rules.video requirements."""

from __future__ import annotations

from pathlib import Path
from intelligence.config import load_config

ROOT = Path(__file__).resolve().parent.parent.parent


def test_all_bespoke_themes_have_video_stream_rules():
    config = load_config(ROOT)
    exact_themes = [
        t for t in config.themes
        if t.get("id") != "domain-fallback" and t.get("micro_topic") not in {None, "any", "*"}
    ]
    for theme in exact_themes:
        stream_rules = theme.get("stream_rules") or theme.get("content_streams") or {}
        video = stream_rules.get("video")
        assert bool(video), f"Theme {theme.get('id')} missing stream_rules.video"
        assert "questions" in video, f"Theme {theme.get('id')} missing video.questions"
        assert len(video["questions"]) >= 1
        assert "focus" in video, f"Theme {theme.get('id')} missing video.focus"
