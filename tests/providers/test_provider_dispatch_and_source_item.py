"""Tests for ProviderResolver, SourceItem model, and provider dispatch."""

from __future__ import annotations

import os
from unittest.mock import patch

from intelligence.ingestion.auth import AuthErrorCode, ProviderAuthManager
from intelligence.ingestion.base import CanonicalContent
from intelligence.ingestion.providers.news_api import NewsAPIProvider
from intelligence.ingestion.providers.resolver import GenericHTTPProvider, ProviderResolver
from intelligence.ingestion.providers.rss import RSSProvider
from intelligence.ingestion.providers.source_item import SourceItem
from intelligence.ingestion.providers.youtube import YouTubeProvider
from intelligence.sources import SourceContract


def test_source_item_creation_and_canonical_conversion():
    item = SourceItem(
        source_id="src-test",
        provider="rss",
        external_id="ext-1",
        url="https://example.com/article",
        title="Breakthrough in Quantum Computing",
        description="Detailed description of the breakthrough",
        published_at="2026-09-18T12:00:00Z",
        retrieved_at="2026-09-18T13:00:00Z",
        author="Alice",
        content="Full text content here",
        license="open_access",
        retention_policy="retain_1_year",
        topics=["quantum"],
        micro_topics=["quantum-algorithms"],
    )

    cc = item.to_canonical_content()
    assert isinstance(cc, CanonicalContent)
    assert cc.source_id == "src-test"
    assert cc.title == "Breakthrough in Quantum Computing"
    assert cc.canonical_url == "https://example.com/article"

    roundtrip = SourceItem.from_canonical_content(cc, provider="rss")
    assert roundtrip.source_id == item.source_id
    assert roundtrip.title == item.title
    assert roundtrip.url == item.url


def test_provider_resolver_dispatch():
    resolver = ProviderResolver()

    rss_src = SourceContract(
        id="rss-1",
        name="RSS Source",
        type="rss",
        role="NEWS",
        trust_tier=2,
        region="global",
        country="GLOBAL",
        domains=("tech",),
        topics=("ai",),
        micro_topics=("foundation-models",),
        collection_method="rss",
        url="https://example.com/feed",
    )
    assert isinstance(resolver.resolve(rss_src), RSSProvider)

    yt_src = SourceContract(
        id="yt-1",
        name="YouTube Source",
        type="youtube",
        role="VIDEO",
        trust_tier=2,
        region="global",
        country="GLOBAL",
        domains=("tech",),
        topics=("ai",),
        micro_topics=("foundation-models",),
        collection_method="youtube",
        url="https://youtube.com/channel/test",
    )
    assert isinstance(resolver.resolve(yt_src), YouTubeProvider)

    news_src = SourceContract(
        id="news-1",
        name="News API Source",
        type="news_api",
        role="NEWS",
        trust_tier=2,
        region="global",
        country="GLOBAL",
        domains=("tech",),
        topics=("ai",),
        micro_topics=("foundation-models",),
        collection_method="news_api",
        url="https://newsapi.org/v2/everything",
    )
    assert isinstance(resolver.resolve(news_src), NewsAPIProvider)

    generic_src = SourceContract(
        id="gen-1",
        name="Generic Source",
        type="http",
        role="NEWS",
        trust_tier=3,
        region="global",
        country="GLOBAL",
        domains=("general",),
        topics=("general",),
        micro_topics=("general",),
        collection_method="http",
        url="https://example.com/api",
    )
    assert isinstance(resolver.resolve(generic_src), GenericHTTPProvider)


def test_provider_auth_manager_validation():
    # Missing key
    with patch.dict(os.environ, {}, clear=True):
        res = ProviderAuthManager.validate_provider_auth("gemini")
        assert not res.valid
        assert res.error_code == AuthErrorCode.AUTH_MISSING

    # Invalid placeholder key
    with patch.dict(os.environ, {"GEMINI_API_KEY": "PLACEHOLDER"}):
        res = ProviderAuthManager.validate_provider_auth("gemini")
        assert not res.valid
        assert res.error_code == AuthErrorCode.AUTH_INVALID

    # Structurally valid key
    with patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaSyValidTokenLongEnough123"}):
        res = ProviderAuthManager.validate_provider_auth("gemini")
        assert res.valid
        assert res.error_code is None
