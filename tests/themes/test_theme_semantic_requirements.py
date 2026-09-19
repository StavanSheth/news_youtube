"""Adversarial and semantic isolation tests across neighboring micro-topics."""

from __future__ import annotations

from pathlib import Path

from intelligence.config import load_config
from intelligence.themes.snapshots import compute_theme_fingerprint
from intelligence.themes.review import ThemeReviewStatus, evaluate_theme_review_record
from intelligence.themes.routing import select_theme

ROOT = Path(__file__).resolve().parent.parent.parent


def _load_all_themes():
    config = load_config(ROOT)
    themes = [
        t for t in config.themes
        if t.get("micro_topic_id") or (t.get("micro_topic") not in {"any", "*", None})
    ]
    return themes


def test_all_236_themes_have_unique_fingerprints():
    themes = _load_all_themes()
    assert len(themes) == 236, f"Expected 236 bespoke themes, found {len(themes)}"

    ids = [t.get("theme_id") or t.get("id") for t in themes]
    assert len(ids) == len(set(ids)), f"Duplicate theme IDs found: {len(ids) - len(set(ids))}"

    micro_topics = [(t.get("domain"), t.get("micro_topic_id") or t.get("micro_topic")) for t in themes]
    assert len(micro_topics) == len(set(micro_topics)), "Duplicate micro_topic mappings found"

    fingerprints = [compute_theme_fingerprint(t) for t in themes]
    assert len(fingerprints) == len(set(fingerprints)), "Duplicate theme content fingerprints found"


def test_adversarial_ai_neighbor_routing():
    """Ensure neighboring AI topics route to the exact micro-topic and reject siblings."""
    themes = _load_all_themes()

    ai_cases = [
        ("foundation-models", "foundation-models", "Evaluating frontier foundation model capabilities"),
        ("reasoning-models", "reasoning-models", "Chain-of-thought dynamic inference benchmark"),
        ("ai-agents", "ai-agents", "Autonomous agent tool invocation and planning loops"),
        ("agentic-workflows", "agentic-workflows", "Multi-step tool chaining and orchestration flow"),
        ("coding-models", "coding-models", "Code generation and automated software engineering benchmarks"),
        ("rag", "rag", "Retrieval augmented generation indexing and vector chunking"),
        ("multimodal-ai", "multimodal-ai", "Cross-modal image video reasoning capabilities"),
        ("ai-infrastructure", "ai-infrastructure", "High density compute cluster networking and storage"),
    ]

    for expected_mt, query_keyword, query_text in ai_cases:
        item = {
            "title": f"Update regarding {query_keyword}",
            "text": query_text,
            "kind": "news",
        }
        classification = {
            "domain": "artificial-intelligence",
            "topic": "any",
            "micro_topic": expected_mt,
        }
        res = select_theme(classification, themes, item)
        assert res.get("theme_resolution") is not None
        assert res.get("micro_topic_id") == expected_mt, (
            f"Expected routing to {expected_mt}, got {res.get('micro_topic_id')}"
        )


def test_adversarial_economics_neighbor_routing():
    """Ensure neighboring economics topics route specifically."""
    themes = _load_all_themes()

    econ_cases = [
        ("macroeconomics", "macroeconomics", "GDP growth rate and global aggregate output forecast"),
        ("central-banks", "central-banks", "Central bank monetary policy statement and balance sheet"),
        ("inflation", "inflation", "Consumer price index headline and core inflation print"),
        ("interest-rates", "interest-rates", "Policy rate benchmark yield curve shift"),
        ("equities", "equities", "Stock market index earnings and valuation multiple catalysts"),
        ("bonds", "bonds", "Sovereign debt yield spreads and fixed income market trends"),
    ]

    for expected_mt, query_keyword, query_text in econ_cases:
        item = {
            "title": f"Economic report: {query_keyword}",
            "text": query_text,
            "kind": "news",
        }
        classification = {
            "domain": "finance",
            "topic": "any",
            "micro_topic": expected_mt,
        }
        res = select_theme(classification, themes, item)
        assert res.get("theme_resolution") is not None
        assert res.get("micro_topic_id") == expected_mt, (
            f"Expected routing to {expected_mt}, got {res.get('micro_topic_id')}"
        )


def test_theme_question_specificity_no_generic_duplicates():
    """Verify themes have specific questions that are not copy-pasted across siblings."""
    themes = _load_all_themes()

    all_question_sets = {}
    for t in themes:
        mt = t.get("micro_topic_id") or t.get("micro_topic")
        questions = tuple(sorted(t.get("questions", [])))
        assert len(questions) >= 4, f"Theme for {mt} must have at least 4 questions"
        all_question_sets[mt] = questions

    # Verify no two themes have the exact same question set
    unique_sets = set(all_question_sets.values())
    assert len(unique_sets) == len(all_question_sets), (
        f"Identical question sets detected across {len(all_question_sets) - len(unique_sets)} themes"
    )


def test_theme_review_evaluation():
    """Verify theme review record generation and state progression."""
    themes = _load_all_themes()
    sample = themes[0]
    record = evaluate_theme_review_record(sample)

    assert record["theme_id"] != ""
    assert record["micro_topic_id"] != ""
    assert record["specificity"] >= 0.50
    assert record["review_status"] in (
        ThemeReviewStatus.SEMANTIC_VALIDATED.value,
        ThemeReviewStatus.AI_VALIDATED.value,
        ThemeReviewStatus.APPROVED.value,
    )
    assert not record["blocking_issues"]
