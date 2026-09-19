"""Tests for theme resolution order, stream routing, and fallback traceability."""

from __future__ import annotations

from pathlib import Path
from intelligence.config import load_config
from intelligence.themes import select_theme

ROOT = Path(__file__).resolve().parent.parent.parent


def test_exact_microtopic_theme_resolution():
    config = load_config(ROOT)
    classification = {
        "domain": "artificial-intelligence",
        "topic": "Artificial Intelligence",
        "micro_topic": "foundation-models",
    }
    theme = select_theme(classification, config.themes, {"kind": "news"})

    assert theme["resolution_level"] == "exact_micro_topic"
    assert theme["fallback_used"] is False
    assert theme["fallback_reason"] is None
    assert theme["theme_id"] == "ai-models-tools"
    assert "theme_resolution" in theme


def test_domain_fallback_when_microtopic_unknown():
    config = load_config(ROOT)
    classification = {
        "domain": "cybersecurity",
        "topic": "any",
        "micro_topic": "unknown-nonexistent-subtopic",
    }
    theme = select_theme(classification, config.themes, {"kind": "news"})

    assert theme["resolution_level"] in {"domain_family", "exact_micro_topic"} or theme["fallback_used"] is True
    assert theme["theme_id"] in {"cybersecurity-incident-family", "domain-fallback"}


def test_global_fallback_when_domain_unknown():
    config = load_config(ROOT)
    classification = {
        "domain": "non-existent-domain",
        "topic": "any",
        "micro_topic": "any",
    }
    theme = select_theme(classification, config.themes, {"kind": "news"})

    assert theme["resolution_level"] == "controlled_fallback"
    assert theme["fallback_used"] is True
    assert theme["theme_id"] == "domain-fallback"
    assert theme["resolution_level_code"] == "CONTROLLED_FALLBACK"


def test_stream_specific_video_questions_added():
    config = load_config(ROOT)
    classification = {
        "domain": "artificial-intelligence",
        "topic": "Artificial Intelligence",
        "micro_topic": "ai-agents",
    }
    video_theme = select_theme(classification, config.themes, {"kind": "youtube"})
    assert "main_argument" in video_theme["questions"]
    assert video_theme["resolution_level"] == "exact_micro_topic"
