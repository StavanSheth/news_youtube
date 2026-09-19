"""Tests for controlled fallback behavior and reason transparency."""

from __future__ import annotations

from pathlib import Path
from intelligence.config import load_config
from intelligence.themes import select_theme

ROOT = Path(__file__).resolve().parent.parent.parent


def test_controlled_fallback_reports_trace():
    config = load_config(ROOT)
    classification = {
        "domain": "unknown-domain",
        "topic": "unknown-topic",
        "micro_topic": "unknown-microtopic",
    }
    theme = select_theme(classification, config.themes, {"kind": "news"})

    assert theme["fallback_used"] is True
    assert theme["theme_id"] == "domain-fallback"
    assert theme["fallback_reason"] is not None
    assert theme["resolution_level"] == "controlled_fallback"
    assert "theme_resolution_record" in theme


def test_fallback_does_not_silently_override_configured_topic():
    config = load_config(ROOT)
    classification = {
        "domain": "semiconductors",
        "topic": "Semiconductors",
        "micro_topic": "chip-design",
    }
    theme = select_theme(classification, config.themes, {"kind": "news"})

    assert theme["fallback_used"] is False
    assert theme["resolution_level"] == "exact_micro_topic"
    assert theme["theme_id"] == "semiconductors-chip-design-theme"
