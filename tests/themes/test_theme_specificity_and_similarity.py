"""Tests for theme specificity machinery, boilerplate detection, and similarity metrics."""

from __future__ import annotations

from pathlib import Path
import pytest

from intelligence.config import _load_themes
from intelligence.themes.contracts import ThemeCertificationStatus, certify_theme
from intelligence.themes.quality import (
    classify_theme_resolution_tier,
    is_generic_objective,
    is_generic_questions,
    question_overlap_score,
    theme_similarity_score,
    validate_microtopic_specificity_machinery,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def bespoke_themes():
    themes = _load_themes(ROOT / "config")
    return [t for t in themes if t.get("micro_topic") not in {"any", "*", None}]


def test_theme_resolution_tier_classification():
    assert classify_theme_resolution_tier({"id": "domain-fallback", "domain": "all", "micro_topic": "any"}) == "GLOBAL_FALLBACK"
    assert classify_theme_resolution_tier({"id": "ai-family", "domain": "artificial-intelligence", "micro_topic": "any"}) == "FAMILY_LEVEL"
    assert classify_theme_resolution_tier({"id": "ai-theme", "domain": "artificial-intelligence", "topic": "llm", "micro_topic": "any"}) == "TOPIC_LEVEL"
    assert classify_theme_resolution_tier({"id": "ai-fm-theme", "domain": "artificial-intelligence", "topic": "llm", "micro_topic": "foundation-models"}) == "MICRO_TOPIC_SPECIFIC"


def test_boilerplate_detection():
    generic_theme = {
        "objective": "monitor updates",
        "questions": ["what changed?", "why does it matter?", "what to watch?"],
        "evidence_requirements": ["fact"],
        "significance_rules": {"significant_if": ["important"]},
        "entity_extraction": {"required": []},
        "event_extraction": {"event_types": []},
        "analysis_dimensions": ["basic"],
        "action_rules": {},
        "watch_rules": {},
        "output": {},
    }
    assert is_generic_objective(generic_theme)
    assert is_generic_questions(generic_theme)

    ok, errors = validate_microtopic_specificity_machinery({**generic_theme, "micro_topic": "specific-topic"})
    assert not ok
    assert len(errors) >= 5


def test_all_236_bespoke_themes_pass_specificity_machinery(bespoke_themes):
    assert len(bespoke_themes) >= 236
    for theme in bespoke_themes:
        ok, errors = validate_microtopic_specificity_machinery(theme)
        assert ok, f"Theme {theme.get('id')} failed specificity machinery: {errors}"


def test_theme_similarity_scoring():
    t1 = {
        "questions": ["what changed in foundation models", "evaluating latency benchmarks"],
        "evidence": {"required": ["arxiv", "official_benchmarks"]},
        "analysis_dimensions": ["latency", "throughput", "model_size"],
        "action_rules": {"monitor": ["benchmark_updates"]},
        "output": {"report_type": "deep_dive", "sections": ["summary", "benchmarks"]},
    }
    t2 = dict(t1)
    assert theme_similarity_score(t1, t2) == 1.0

    t3 = {
        "questions": ["what changed in monetary policy", "interest rates trajectory"],
        "evidence": {"required": ["central_bank_statement"]},
        "analysis_dimensions": ["inflation", "employment"],
        "action_rules": {"monitor": ["fomc_calendar"]},
        "output": {"report_type": "brief", "sections": ["summary"]},
    }
    sim = theme_similarity_score(t1, t3)
    assert sim < 0.30
    assert question_overlap_score(t1, t3) < 0.20


def test_theme_certification_lifecycle(bespoke_themes):
    sample = bespoke_themes[0]
    status, blocking = certify_theme(sample, other_themes=[bespoke_themes[1]])
    assert status == ThemeCertificationStatus.CERTIFIED.value
    assert len(blocking) == 0

    # Malformed theme is quarantined
    bad_theme = {"id": "bad-theme", "version": "1.0.0"}
    bad_status, bad_blocking = certify_theme(bad_theme)
    assert bad_status in (ThemeCertificationStatus.QUARANTINED.value, ThemeCertificationStatus.UNDER_TEST.value)
    assert len(bad_blocking) > 0
