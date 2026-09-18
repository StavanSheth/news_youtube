"""Phase 2B tests for source and event diversity filtering."""

from __future__ import annotations

from intelligence.rag.diversity import apply_diversity_filtering


def test_source_diversity_caps_chunks_per_source():
    # 5 chunks from the same source, 1 from another
    chunks = [
        {"id": f"c{i}", "text": f"Chunk {i}", "metadata": {"source_id": "monopoly_feed", "content_id": f"item{i}"}}
        for i in range(5)
    ] + [
        {"id": "c5", "text": "Chunk 5", "metadata": {"source_id": "diverse_feed", "content_id": "item5"}}
    ]

    # Target 3 chunks, max 2 per source
    selected, diag = apply_diversity_filtering(chunks, target_count=3, max_per_source=2)
    assert len(selected) == 3
    sources = [c["metadata"]["source_id"] for c in selected]
    assert sources.count("monopoly_feed") <= 2
    assert "diverse_feed" in sources
    assert diag["diversity_skipped"] >= 1
