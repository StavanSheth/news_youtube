"""Tests for decoupled item-level normalization, classification, and theme routing."""

from intelligence.application.item_processor import ItemProcessor, SourceItem


def test_item_processor_normalizes_and_classifies():
    processor = ItemProcessor(
        themes=[
            {
                "id": "theme-ai",
                "domain": "artificial-intelligence",
                "micro_topic": "foundation-models",
                "questions": ["what_changed"],
            }
        ]
    )
    source = SourceItem(
        id="item-001",
        source="Ars Technica",
        title="Foundation model benchmark release",
        url="https://arstechnica.test/ai/reasoning-model-compute",
        text="New foundation model capability and base model inference benchmark.",
        published_at="2026-09-18T10:00:00+00:00",
        priority=8,
    )
    processed = processor.process_item(source)

    assert processed.item_id == "item-001"
    assert processed.source_id.startswith("source-")
    assert processed.content_id.startswith("content-")
    assert processed.status == "PROCESSED"
    assert processed.theme["id"] == "theme-ai"
    assert len(processed.micro_topic_jobs) >= 1
    job = processed.micro_topic_jobs[0]
    assert job["content_id"] == processed.content_id
    assert job["source_id"] == processed.source_id
    assert "classification" in job
    assert "theme" in job


def test_item_processor_deterministic_identifiers():
    processor = ItemProcessor()
    raw = {
        "id": "raw-01",
        "source": "TechDaily",
        "title": "Quantum Breakthrough",
        "url": "https://tech.test/quantum",
        "text": "Quantum computing room temperature test.",
        "published_at": "2026-09-18T12:00:00+00:00",
    }
    first = processor.process_item(raw)
    second = processor.process_item(raw)
    assert first.content_id == second.content_id
    assert first.source_id == second.source_id
