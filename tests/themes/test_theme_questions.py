"""Tests for theme analysis questions completeness and topic specificity."""

from __future__ import annotations

from pathlib import Path
from intelligence.config import load_config

ROOT = Path(__file__).resolve().parent.parent.parent


def test_all_bespoke_themes_have_sufficient_questions():
    config = load_config(ROOT)
    exact_themes = [
        t for t in config.themes
        if t.get("id") != "domain-fallback" and t.get("micro_topic") not in {None, "any", "*"}
    ]
    assert len(exact_themes) == 236
    for theme in exact_themes:
        questions = theme.get("questions", [])
        assert len(questions) >= 4, f"Theme {theme.get('id')} has fewer than 4 questions"


def test_questions_are_topic_specific():
    config = load_config(ROOT)
    exact_themes = [
        t for t in config.themes
        if t.get("id") != "domain-fallback" and t.get("micro_topic") not in {None, "any", "*"}
    ]
    for theme in exact_themes:
        mt_id = theme.get("micro_topic")
        normalized_mt = mt_id.replace("-", "_")
        q_text = " ".join(str(q).lower() for q in theme.get("questions", []))
        # At least one question contains the micro-topic name or term
        assert normalized_mt in q_text or mt_id in q_text, f"Questions for {theme.get('id')} do not mention {mt_id}"
