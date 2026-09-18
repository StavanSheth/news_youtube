"""Phase 2A tests for deterministic theme routing and observable fallbacks."""

from __future__ import annotations

from pathlib import Path
from intelligence.config import load_config
from intelligence.themes import select_theme

ROOT = Path(__file__).parents[2]


def test_theme_routing_exact_microtopic():
    config = load_config(ROOT)
    classification = {
        "domain": "artificial-intelligence",
        "topic": "Artificial Intelligence",
        "topic_key": "artificial-intelligence",
        "micro_topic": "ai-agents",
        "micro_topic_id": "ai-agents",
    }
    item = {"kind": "news"}
    theme = select_theme(classification, config.themes, item)

    assert theme["fallback_used"] is False
    assert theme["fallback_reason"] is None
    record = theme["theme_resolution"]
    assert record["requested_level"] == "micro_topic"
    assert record["resolved_level"] == "micro_topic"
    assert record["fallback_used"] is False


def test_theme_routing_controlled_fallback_record():
    themes = [
        {"id": "domain-fallback", "domain": "all", "questions": ["what_changed"], "theme_origin": "FALLBACK"}
    ]
    classification = {
        "domain": "unknown-domain",
        "topic": "Unknown",
        "micro_topic": "unknown-topic",
    }
    item = {"kind": "news"}
    theme = select_theme(classification, themes, item)

    assert theme["fallback_used"] is True
    assert theme["fallback_reason"] == "no_exact_topic_or_domain_theme"
    record = theme["theme_resolution"]
    assert record["requested_level"] == "micro_topic"
    assert record["resolved_level"] == "controlled_fallback"
    assert record["fallback_used"] is True
    assert record["fallback_reason"] is not None


def test_theme_routing_domain_fallback():
    themes = [
        {
            "id": "cyber-family",
            "domain": "cybersecurity",
            "topic": "any",
            "micro_topic": "any",
            "questions": ["cve_details"],
        },
        {"id": "domain-fallback", "domain": "all", "questions": ["what_changed"]},
    ]
    classification = {
        "domain": "cybersecurity",
        "topic": "Cybersecurity",
        "micro_topic": "ransomware-unconfigured-leaf",
    }
    item = {"kind": "news"}
    theme = select_theme(classification, themes, item)

    assert theme["fallback_used"] is True
    assert theme["theme_resolution"]["resolved_level"] == "domain"
    assert theme["theme_resolution"]["fallback_used"] is True
