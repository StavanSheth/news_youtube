from __future__ import annotations

from pathlib import Path

from intelligence.production import RepositoryState, relevance, topic_matches
from intelligence.schema import normalized_analysis


def test_multi_topic_classifier_respects_thresholds():
    item = {
        "title": "AI agents reshape markets",
        "text": "Artificial intelligence agents affect earnings and inflation.",
    }
    topics = [
        {
            "name": "AI",
            "key": "ai",
            "enabled": True,
            "keywords": ["artificial intelligence", "agents"],
            "classification_threshold": 0.25,
        },
        {
            "name": "Finance",
            "key": "finance",
            "enabled": True,
            "keywords": ["markets", "earnings", "inflation"],
            "classification_threshold": 0.25,
        },
        {
            "name": "Health",
            "key": "health",
            "enabled": True,
            "keywords": ["trial"],
            "classification_threshold": 0.25,
        },
    ]
    matches = topic_matches(item, topics)
    assert {match["key"] for match in matches} == {"finance", "ai"}


def test_schema_rejects_invalid_and_normalizes_duplicates():
    payload = normalized_analysis(
        {"facts": ["One", "One"], "interpretation": "Inference", "confidence": 2}
    )
    assert payload["facts"] == ["One"]
    assert payload["interpretation"] == ["Inference"]
    assert payload["confidence"] == 1.0


def test_compact_state_and_failure_backoff(tmp_path: Path):
    for name, value in (
        ("processed_videos.json", "{}"),
        ("processed_news.json", "{}"),
        ("processing_state.json", '{"runs": [], "recent_items": []}'),
        ("failed_items.json", "{}"),
    ):
        (tmp_path / name).write_text(value)
    state = RepositoryState(
        tmp_path, {"max_processed_items": 2, "max_failed_items": 2, "max_recent_runs": 2}
    )
    item = {
        "id": "x",
        "kind": "news",
        "title": "AI",
        "text": "AI",
        "url": "https://example.com",
        "published_at": "2026-01-01T00:00:00+00:00",
    }
    state.success(item, [{"key": "ai"}], 0.8, "NEW")
    state.failure({**item, "id": "failure"}, RuntimeError("temporary"))
    state.finish({"started": "now"}, [])
    assert state.news["x"]["status"] == "success"
    assert state.failures["failure"]["status"] == "transient"
    assert not state.retry_due("failure")


def test_relevance_uses_multiple_configurable_signals():
    score = relevance(
        {"priority": 10, "text": "x" * 1500, "published_at": "2099-01-01T00:00:00+00:00"},
        [{"score": 1.0}],
        {
            "topic_relevance": 0.4,
            "source_priority": 0.2,
            "recency": 0.2,
            "content_completeness": 0.2,
        },
    )
    assert score == 1.0
