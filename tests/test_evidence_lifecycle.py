"""Tests for evidence lifecycle, chunking, and context budgeting."""

from intelligence.evidence import CharacterChunker, Chunk, Evidence, deterministic_chunks, semantic_chunks
from intelligence.rag.budget import ContextBudgeter


def test_chunk_creation_and_immutability():
    chunk = Chunk(
        chunk_id="c1:0",
        text="Sample chunk text",
        content_id="c1",
        source_id="s1",
        span_start=0,
        span_end=17,
        span_id="c1:span:0:17",
        metadata={"trust_tier": 2},
    )
    assert chunk.chunk_id == "c1:0"
    assert chunk.span_id == "c1:span:0:17"
    data = chunk.to_dict()
    assert data["id"] == "c1:0"
    assert data["text"] == "Sample chunk text"
    assert data["metadata"]["trust_tier"] == 2

    # Roundtrip from_dict
    reconstructed = Chunk.from_dict(data)
    assert reconstructed.chunk_id == chunk.chunk_id
    assert reconstructed.text == chunk.text
    assert reconstructed.span_id == chunk.span_id


def test_character_chunker_generates_spans_and_provenance():
    chunker = CharacterChunker(size=50, overlap=10)
    item = {
        "id": "doc-1",
        "url": "https://example.test/news/1",
        "title": "AI Breakthrough",
        "source": "TechDaily",
        "text": "A" * 120,
        "kind": "article",
        "published_at": "2026-09-18T10:00:00+00:00",
        "metadata": {
            "trust_tier": 1,
            "retrieved_at": "2026-09-18T10:05:00+00:00",
            "classification": {
                "domain": "ai",
                "micro_topic_id": "breakthroughs",
                "micro_topic": "breakthroughs",
                "signals": ["A"],
            },
        },
    }
    chunks = chunker.chunk_item(item)
    assert len(chunks) >= 3
    for i, c in enumerate(chunks):
        assert c.content_id
        assert c.span_id.startswith(f"{c.content_id}:span:")
        assert c.span_start >= 0
        assert c.span_end > c.span_start
        assert c.metadata["provenance_status"] == "VALID"
        assert c.metadata["provenance"]["source_url"] == "https://example.test/news/1"

    # Verify deterministic_chunks helper produces compatible output
    dict_chunks = deterministic_chunks(item, size=50, overlap=10)
    assert len(dict_chunks) == len(chunks)
    assert dict_chunks[0]["id"] == chunks[0].chunk_id
    assert semantic_chunks(item, size=50, overlap=10) == dict_chunks


def test_evidence_model_preserves_provenance_and_identifiers():
    chunk_data = {
        "id": "content1:0",
        "text": "Evidence fact statement",
        "metadata": {
            "content_id": "content1",
            "source_id": "source1",
            "span_id": "content1:span:0:23",
            "url": "https://example.test/story",
            "title": "Story Title",
            "trust_tier": 1,
            "published_at": "2026-09-18T00:00:00+00:00",
            "retrieved_at": "2026-09-18T01:00:00+00:00",
            "provenance": {"evidence_id": "ev-1", "source_url": "https://example.test/story"},
            "micro_topic_id": "ai-models",
        },
    }
    evidence = Evidence.from_chunk(chunk_data)
    assert evidence.content_id == "content1"
    assert evidence.source_id == "source1"
    assert evidence.url == "https://example.test/story"
    assert evidence.micro_topic_id == "ai-models"
    assert evidence.text == "Evidence fact statement"

    ev_dict = evidence.to_dict()
    assert ev_dict["content_id"] == "content1"
    assert ev_dict["trust_tier"] == 1


def test_context_budgeter_enforces_hard_limits_and_traces():
    budgeter = ContextBudgeter(max_chars=100, max_tokens=30, max_items=2)
    chunks = [
        {"id": "c1", "text": "Short chunk 1 " * 3},  # ~42 chars
        {"id": "c2", "text": "Short chunk 2 " * 3},  # ~42 chars
        {"id": "c3", "text": "Short chunk 3 " * 3},  # ~42 chars (should exceed max_chars/max_items)
    ]
    bounded, trace = budgeter.enforce_budget(chunks)
    assert len(bounded) == 2
    assert trace["items_selected"] == 2
    assert trace["items_dropped"] >= 1
    assert trace["chars_used"] <= 100
    assert trace["tokens_used"] <= 30
    assert any(d["action"] == "INCLUDED" for d in trace["details"])
    assert any("DROPPED" in d["action"] for d in trace["details"])


def test_context_budgeter_truncates_first_chunk_if_oversized():
    budgeter = ContextBudgeter(max_chars=50, max_tokens=20, max_items=2)
    giant_chunk = [{"id": "giant", "text": "X" * 200}]
    bounded, trace = budgeter.enforce_budget(giant_chunk)
    assert len(bounded) == 1
    assert len(bounded[0]["text"]) <= 50
    assert bounded[0]["metadata"]["truncated_for_budget"] is True
    assert trace["truncated_items"] == 1
