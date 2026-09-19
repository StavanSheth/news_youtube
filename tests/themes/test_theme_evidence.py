"""Tests for theme evidence requirements."""

from __future__ import annotations

from pathlib import Path
from intelligence.config import load_config

ROOT = Path(__file__).resolve().parent.parent.parent


def test_all_bespoke_themes_have_evidence_requirements():
    config = load_config(ROOT)
    exact_themes = [
        t for t in config.themes
        if t.get("id") != "domain-fallback" and t.get("micro_topic") not in {None, "any", "*"}
    ]
    for theme in exact_themes:
        ev_reqs = theme.get("evidence_requirements")
        if not ev_reqs and isinstance(theme.get("evidence"), dict):
            ev_reqs = theme["evidence"].get("required", [])
        assert bool(ev_reqs), f"Theme {theme.get('id')} missing evidence requirements"
        assert len(ev_reqs) >= 1
        assert "primary_source_verification" in ev_reqs or "fact" in ev_reqs or any("source" in e for e in ev_reqs)
