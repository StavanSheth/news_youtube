"""Live source to RAG pipeline integration (explicit live mode only)."""

from __future__ import annotations

import os
import pytest
from intelligence.ingestion.providers.rss import RSSProvider
from intelligence.rag.manager import RAGManager
from intelligence.rag.query import RetrievalRequest
from intelligence.sources import SourceContract


def test_live_source_to_rag_pipeline():
    """Verify live RSS source flows into RAG when RUN_LIVE_TESTS is enabled."""
    if not os.environ.get("RUN_LIVE_TESTS") and not os.environ.get("LIVE_SOURCE_TESTS"):
        pytest.skip("Live source-to-RAG tests skipped in deterministic CI.")

    source = SourceContract.from_mapping({
        "id": "bbc-news-rag-live",
        "name": "BBC News",
        "type": "rss",
        "role": "NEWS",
        "trust_tier": 2,
        "url": "http://feeds.bbci.co.uk/news/rss.xml",
        "enabled": True,
    })

    provider = RSSProvider(timeout=10)
    content_items = provider.collect(source, live=True)
    if not content_items:
        pytest.skip("Live feed returned 0 items. Network may be unreachable.")

    manager = RAGManager(settings={"retrieval_top_k": 3})
    item = content_items[0]
    manager.index_item({
        "id": "live-chk-1",
        "title": item.title,
        "text": item.summary_text or item.body_text,
        "url": item.canonical_url,
        "published_at": item.published_at,
        "metadata": {
            "source_id": item.source_id,
            "content_id": item.content_id,
            "micro_topic_id": "macroeconomics",
            "published_at": item.published_at,
            "trust_tier": 2,
            "url": item.canonical_url,
        },
    })

    req = RetrievalRequest(
        query="news",
        micro_topic_id="macroeconomics",
        theme_id="theme-macroeconomics",
    )
    result = manager.retrieve(req)
    assert result.status == "OK"
    assert len(result.chunks) >= 1
