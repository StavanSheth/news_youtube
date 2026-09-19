"""Tests for micro-topic isolation between neighboring topics."""

from __future__ import annotations

from pathlib import Path
from intelligence.config import load_config
from intelligence.themes import select_theme

ROOT = Path(__file__).resolve().parent.parent.parent


def test_neighboring_ai_topics_isolated():
    config = load_config(ROOT)
    themes = config.themes

    models = select_theme(
        {"domain": "artificial-intelligence", "topic": "Artificial Intelligence", "micro_topic": "foundation-models"},
        themes,
        {"kind": "news"},
    )
    agents = select_theme(
        {"domain": "artificial-intelligence", "topic": "Artificial Intelligence", "micro_topic": "ai-agents"},
        themes,
        {"kind": "news"},
    )
    rag = select_theme(
        {"domain": "artificial-intelligence", "topic": "Artificial Intelligence", "micro_topic": "rag"},
        themes,
        {"kind": "news"},
    )

    assert models["theme_id"] != agents["theme_id"]
    assert agents["theme_id"] != rag["theme_id"]
    assert models["theme_id"] != rag["theme_id"]
    assert set(models["questions"]) != set(agents["questions"])
    assert set(agents["questions"]) != set(rag["questions"])


def test_neighboring_semiconductor_topics_isolated():
    config = load_config(ROOT)
    themes = config.themes

    fabs = select_theme(
        {"domain": "semiconductors", "topic": "Semiconductors", "micro_topic": "fabs"},
        themes,
        {"kind": "news"},
    )
    foundries = select_theme(
        {"domain": "semiconductors", "topic": "Semiconductors", "micro_topic": "foundries"},
        themes,
        {"kind": "news"},
    )
    gpus = select_theme(
        {"domain": "semiconductors", "topic": "Semiconductors", "micro_topic": "gpus"},
        themes,
        {"kind": "news"},
    )

    assert fabs["theme_id"] != foundries["theme_id"]
    assert foundries["theme_id"] != gpus["theme_id"]
    assert fabs["theme_id"] == "semiconductors-fabs-theme"
    assert foundries["theme_id"] == "semiconductors-foundries-theme"
    assert gpus["theme_id"] == "semiconductors-gpus-theme"
