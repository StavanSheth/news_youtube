"""Live network validation for RSS feeds (explicit live mode only)."""

from __future__ import annotations

import os
import pytest
from intelligence.ingestion.providers.rss import RSSProvider
from intelligence.sources import SourceContract


def test_rss_live_network_validation():
    """Verify live RSS feed network fetching and parsing when explicitly enabled."""
    if not os.environ.get("RUN_LIVE_TESTS") and not os.environ.get("LIVE_SOURCE_TESTS"):
        pytest.skip("Live network tests skipped in deterministic CI. Set RUN_LIVE_TESTS=1 to execute.")

    source = SourceContract.from_mapping({
        "id": "bbc-news-live",
        "name": "BBC News Live",
        "type": "rss",
        "role": "NEWS",
        "trust_tier": 2,
        "url": "http://feeds.bbci.co.uk/news/rss.xml",
        "enabled": True,
    })

    provider = RSSProvider(timeout=10)
    result = provider.validate(source, live=True)
    assert result.reachable
    assert result.status in ("READY", "PASS")
    assert result.items_seen > 0
