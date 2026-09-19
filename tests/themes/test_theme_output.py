"""Tests for theme output requirements and report types."""

from __future__ import annotations

from pathlib import Path
from intelligence.config import load_config

ROOT = Path(__file__).resolve().parent.parent.parent


def test_all_bespoke_themes_have_valid_output_structure():
    config = load_config(ROOT)
    valid_reports = set(config.taxonomy["report_types"])
    exact_themes = [
        t for t in config.themes
        if t.get("id") != "domain-fallback" and t.get("micro_topic") not in {None, "any", "*"}
    ]
    for theme in exact_themes:
        output = theme.get("output") or theme.get("output_requirements") or {}
        assert bool(output), f"Theme {theme.get('id')} missing output requirements"
        report_type = output.get("report_type")
        assert report_type in valid_reports, f"Invalid report_type {report_type} in {theme.get('id')}"
        sections = output.get("sections", [])
        assert len(sections) >= 3, f"Theme {theme.get('id')} has fewer than 3 output sections"
