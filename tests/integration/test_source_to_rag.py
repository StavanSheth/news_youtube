"""Integration tests verifying the complete Source -> CanonicalContent -> RAG -> ContextPacket pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock

from intelligence.evidence.chunks import Chunker
from intelligence.ingestion.base import CanonicalContent
from intelligence.ingestion.providers.news_api import NewsAPIProvider
from intelligence.ingestion.providers.rss import RSSProvider
from intelligence.ingestion.providers.youtube import YouTubeProvider
from intelligence.ingestion.youtube.quota import YouTubeQuotaTracker
from intelligence.rag.eligibility import check_chunk_eligibility
from intelligence.rag.manager import RAGManager
from intelligence.rag.query import RetrievalRequest
from intelligence.sources import SourceContract


def test_rss_to_rag_integration():
    """Verify RSS feed items flow through CanonicalContent -> Chunks -> RAG index -> ContextPacket."""
    sample_feed_xml = b"""<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <title>Frontier AI News</title>
        <item>
          <title>New Foundation Model Release 2026</title>
          <link>https://technews.test/fm-release</link>
          <pubDate>Fri, 18 Sep 2026 10:00:00 GMT</pubDate>
          <description>Frontier foundation model exhibits state of the art reasoning performance on math benchmarks.</description>
        </item>
      </channel>
    </rss>"""

    source = SourceContract.from_mapping({
        "id": "tech-rss-source",
        "name": "Tech RSS Source",
        "type": "rss",
        "role": "NEWS",
        "trust_tier": 1,
        "url": "https://technews.test/feed.xml",
        "micro_topics": ["foundation-models"],
        "enabled": True,
    })

    # 1. Collect using RSSProvider with mock parser
    import feedparser
    parsed = feedparser.parse(sample_feed_xml)
    provider = RSSProvider(custom_parser=lambda url: parsed)
    content_items = provider.collect(source)
    assert len(content_items) == 1
    item = content_items[0]
    assert isinstance(item, CanonicalContent)
    inv_ok, _ = item.validate_invariants()
    assert inv_ok

    # 2. Chunking
    chunks = Chunker.deterministic({
        "id": item.content_id,
        "source": item.source_id,
        "title": item.title,
        "url": item.canonical_url,
        "text": item.body_text or item.summary_text,
        "published_at": item.published_at,
        "metadata": {
            "source_id": item.source_id,
            "content_id": item.content_id,
            "micro_topic_id": "foundation-models",
            "trust_tier": 1,
        },
    })
    assert len(chunks) >= 1

    # 3. Eligibility
    req = RetrievalRequest(
        query="foundation model reasoning benchmarks",
        micro_topic_id="foundation-models",
        theme_id="theme-foundation-models",
    )
    for c in chunks:
        c["metadata"] = {
            "source_id": item.source_id,
            "content_id": item.content_id,
            "micro_topic_id": "foundation-models",
            "published_at": item.published_at,
            "trust_tier": 1,
            "url": item.canonical_url,
        }
        ok, reason = check_chunk_eligibility(c, req)
        assert ok, f"Chunk rejected: {reason}"

    # 4. RAG Index & Retrieval
    manager = RAGManager(settings={"retrieval_top_k": 5})
    for c in chunks:
        manager.index_item({
            "id": c["chunk_id"],
            "title": item.title,
            "text": c["text"],
            "url": item.canonical_url,
            "published_at": item.published_at,
            "metadata": c["metadata"],
        })

    retrieval_res = manager.retrieve(req)
    assert retrieval_res.status == "OK"
    assert len(retrieval_res.chunks) >= 1
    packet = retrieval_res.context_packet
    assert "retrieved_evidence" in packet
    assert packet["micro_topic_id"] == "foundation-models"


def test_news_api_to_rag_integration(monkeypatch):
    """Verify News API response flows through CanonicalContent -> Chunker -> RAG -> ContextPacket."""
    monkeypatch.setenv("TEST_NEWS_KEY", "news-key-valid")
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "ok",
        "articles": [
            {
                "source": {"id": "reuters", "name": "Reuters"},
                "title": "Autonomous AI Agents Deploy in Enterprise Workflows",
                "url": "https://reuters.test/ai-agents",
                "publishedAt": "2026-09-18T11:00:00Z",
                "description": "Enterprise software teams deploy autonomous agentic workflows with strict verification.",
            }
        ],
    }
    mock_http.get.return_value = mock_resp

    source = SourceContract.from_mapping({
        "id": "reuters-news-api",
        "name": "Reuters API",
        "type": "news_api",
        "role": "NEWS",
        "trust_tier": 1,
        "url": "https://api.reuters.test/v2/articles",
        "authentication_required": True,
        "authentication_env_var": "TEST_NEWS_KEY",
        "micro_topics": ["ai-agents"],
        "enabled": True,
    })

    provider = NewsAPIProvider(http_client=mock_http)
    content_items = provider.collect(source)
    assert len(content_items) == 1
    item = content_items[0]
    inv_ok, _ = item.validate_invariants()
    assert inv_ok

    manager = RAGManager(settings={"retrieval_top_k": 5})
    manager.index_item({
        "id": "chk-news-1",
        "title": item.title,
        "text": item.summary_text,
        "url": item.canonical_url,
        "published_at": item.published_at,
        "metadata": {
            "source_id": item.source_id,
            "content_id": item.content_id,
            "micro_topic_id": "ai-agents",
            "trust_tier": 1,
            "url": item.canonical_url,
            "published_at": item.published_at,
        },
    })

    req = RetrievalRequest(
        query="autonomous AI agents enterprise workflows",
        micro_topic_id="ai-agents",
        theme_id="theme-ai-agents",
    )
    result = manager.retrieve(req)
    assert result.status == "OK"
    assert len(result.chunks) >= 1
    assert result.context_packet["micro_topic_id"] == "ai-agents"


def test_youtube_to_rag_integration(monkeypatch):
    """Verify YouTube video items flow through CanonicalContent -> RAG -> ContextPacket."""
    monkeypatch.setenv("TEST_YT_KEY", "yt-key-valid")
    mock_http = MagicMock()

    # channels response (uploads playlist)
    resp_channels = MagicMock()
    resp_channels.status_code = 200
    resp_channels.content = b'{"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU_test"}}}]}'
    resp_channels.json.return_value = {
        "items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU_test"}}}]
    }

    # playlistItems response
    resp_playlist = MagicMock()
    resp_playlist.status_code = 200
    resp_playlist.content = b'{"items": [{"contentDetails": {"videoId": "vid-123"}, "snippet": {"title": "Reasoning Models Deep Dive", "publishedAt": "2026-09-18T09:00:00Z", "description": "Analysis of dynamic test time compute scaling."}}]}'
    resp_playlist.json.return_value = {
        "items": [
            {
                "contentDetails": {"videoId": "vid-123"},
                "snippet": {
                    "title": "Reasoning Models Deep Dive",
                    "publishedAt": "2026-09-18T09:00:00Z",
                    "description": "Analysis of dynamic test time compute scaling.",
                },
            }
        ]
    }
    mock_http.get.side_effect = [resp_channels, resp_playlist]

    source = SourceContract.from_mapping({
        "id": "deepmind-yt-channel",
        "name": "DeepMind YouTube",
        "type": "youtube",
        "role": "VIDEO",
        "trust_tier": 1,
        "url": "https://youtube.com/channel/UC_test",
        "authentication_required": True,
        "authentication_env_var": "TEST_YT_KEY",
        "micro_topics": ["reasoning-models"],
        "enabled": True,
        "metadata": {"id": "UC_test"},
    })

    quota = YouTubeQuotaTracker(max_units_per_run=50)
    provider = YouTubeProvider(quota_tracker=quota, http_client=mock_http)
    content_items = provider.collect(source)
    assert len(content_items) == 1
    item = content_items[0]
    inv_ok, _ = item.validate_invariants()
    assert inv_ok

    manager = RAGManager(settings={"retrieval_top_k": 5})
    manager.index_item({
        "id": "chk-yt-1",
        "title": item.title,
        "text": item.summary_text,
        "url": item.canonical_url,
        "published_at": item.published_at,
        "metadata": {
            "source_id": item.source_id,
            "content_id": item.content_id,
            "micro_topic_id": "reasoning-models",
            "trust_tier": 1,
            "url": item.canonical_url,
            "published_at": item.published_at,
        },
    })

    req = RetrievalRequest(
        query="dynamic test time compute reasoning models",
        micro_topic_id="reasoning-models",
        theme_id="theme-reasoning-models",
    )
    res = manager.retrieve(req)
    assert res.status == "OK"
    assert len(res.chunks) >= 1
    assert res.context_packet["micro_topic_id"] == "reasoning-models"


def test_quarantined_source_strictly_blocked_from_rag():
    """Verify quarantined sources cannot enter RAG or ContextPacket under any circumstances."""
    chunk = {
        "id": "chk-quar",
        "text": "Leaked information from untrusted blog",
        "metadata": {
            "source_id": "quarantined-source",
            "content_id": "cnt-quar",
            "micro_topic_id": "foundation-models",
            "quarantined": True,
            "published_at": "2026-09-18T10:00:00Z",
        },
    }
    req = RetrievalRequest(
        query="foundation models leak",
        micro_topic_id="foundation-models",
        theme_id="theme-foundation-models",
    )
    ok, reason = check_chunk_eligibility(chunk, req)
    assert not ok
    assert reason == "QUARANTINED_SOURCE"

    # Also test disabled sources list in check_chunk_eligibility
    ok_disabled, reason_disabled = check_chunk_eligibility(
        {"id": "chk-1", "text": "text", "metadata": {"source_id": "bad-src", "content_id": "c1"}},
        disabled_sources={"bad-src"},
    )
    assert not ok_disabled
    assert reason_disabled == "DISABLED_SOURCE"
