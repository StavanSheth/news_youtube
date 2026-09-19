"""Live network validation for News API (explicit live mode only)."""

from __future__ import annotations

import os
import pytest
from intelligence.ingestion.providers.news_api import NewsAPIProvider
from intelligence.sources import SourceContract


def test_news_api_live_network_validation():
    """Verify live News API fetching when credentials exist."""
    api_key = os.environ.get("NEWS_API_KEY", "").strip()
    if not api_key:
        pytest.skip("NEWS_API_KEY not configured. Skipping live test.")

    source = SourceContract.from_mapping({
        "id": "news-api-live",
        "name": "Live News API",
        "type": "news_api",
        "role": "NEWS",
        "trust_tier": 2,
        "url": "https://newsapi.org/v2/top-headlines?language=en",
        "authentication_required": True,
        "authentication_env_var": "NEWS_API_KEY",
        "enabled": True,
    })

    provider = NewsAPIProvider()
    result = provider.validate(source, live=True)
    assert result.authenticated
    assert result.status in ("READY", "PASS")
