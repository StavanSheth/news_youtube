from datetime import datetime
from pathlib import Path

from intelligence.classification import classify, relevance_score
from intelligence.config import load_config
from intelligence.models import SourceItem
from intelligence.render import html_digest, markdown_digest
from intelligence.state import StateStore


def test_load_config_has_topic_requirements():
    root = Path(__file__).parents[1]
    config = load_config(root)
    assert config.topics[0]["extraction_requirements"]
    assert config.settings["gemini"]["chunk_size"] > 0


def test_topic_classification_and_scoring():
    item = SourceItem(
        "a",
        "news",
        "New AI model benchmark",
        "https://example.com",
        "An artificial intelligence model and new AI agent",
        priority=2,
    )
    topics = [{"name": "AI", "keywords": ["AI", "model", "agent"]}]
    matches = classify(item.text, topics)
    assert matches[0]["topic"]["name"] == "AI"
    assert (
        relevance_score(
            item,
            matches,
            {
                "topic_match_weight": 0.45,
                "keyword_match_weight": 0.2,
                "source_priority_weight": 0.2,
                "recency_weight": 0.15,
            },
        )
        > 0.5
    )


def test_state_deduplicates_and_records_failure(tmp_path):
    (tmp_path / "processed_videos.json").write_text("{}")
    (tmp_path / "processed_news.json").write_text("{}")
    (tmp_path / "processing_state.json").write_text('{"runs": [], "recent_items": []}')
    (tmp_path / "failed_items.json").write_text("{}")
    state = StateStore(tmp_path)
    state.success({"id": "video", "kind": "youtube"}, {"facts": []})
    state.failure("article", ValueError("temporary RSS failure"))
    state.save()
    restored = StateStore(tmp_path)
    assert restored.is_processed("video", "youtube")
    assert restored.failures["article"]["attempts"] == 1


def test_report_contains_separate_fact_and_inference():
    analyses = [
        {
            "item": {"title": "Story", "url": "https://example.com", "source": "Example"},
            "topics": ["AI"],
            "score": 0.8,
            "facts": ["A source claim"],
            "interpretation": ["AI inference"],
            "actionable_insights": ["Try this"],
            "routine": {"Morning": ["Review sources"]},
        }
    ]
    markdown = markdown_digest(analyses, datetime(2026, 1, 1))
    html = html_digest(analyses, datetime(2026, 1, 1), "{{DATE}} {{EDITION}} {{CONTENT}}")
    assert "Source facts" in markdown and "AI interpretation" in markdown
    assert "Story" in html and "Read or watch source" in html
