"""Opt-in live integration tests for source acceptance.

These tests make real network requests and are SKIPPED by default.
Run with:
    RUN_LIVE_SOURCE_TESTS=1 pytest tests/integration/source_validation/test_live_sources.py
"""
from __future__ import annotations

import os
from pathlib import Path
import pytest

from intelligence.source_validation import SourceAcceptanceEngine
from intelligence.sources import SourceAcceptanceStatus

ROOT = Path(__file__).parents[3]
SKIP_LIVE = os.environ.get("RUN_LIVE_SOURCE_TESTS") != "1"


@pytest.mark.skipif(SKIP_LIVE, reason="Opt-in only. Set RUN_LIVE_SOURCE_TESTS=1 to run.")
class TestLiveSources:
    def test_live_rss_acceptance(self):
        engine = SourceAcceptanceEngine(timeout=10, live=True)
        source = {
            "id": "live-test-bbc",
            "name": "BBC News",
            "type": "rss",
            "role": "NEWS",
            "feed_url": "https://feeds.bbci.co.uk/news/world/rss.xml",
            "enabled": True,
            "license_status": "PERMITTED",
            "retention_policy": "REQUIRED",
        }
        result = engine.evaluate_source(source)
        assert result.checked_at is not None
        assert result.latency_ms > 0
        assert result.reachable

    def test_live_unreachable_source_fails_cleanly(self):
        engine = SourceAcceptanceEngine(timeout=5, live=True)
        source = {
            "id": "live-test-unreachable",
            "name": "Nonexistent Domain",
            "type": "rss",
            "role": "NEWS",
            "feed_url": "https://this-domain-does-not-exist-xyz123987.org/feed.xml",
            "enabled": True,
            "license_status": "PERMITTED",
            "retention_policy": "REQUIRED",
        }
        result = engine.evaluate_source(source)
        assert not result.is_ready
        assert result.status == SourceAcceptanceStatus.QUARANTINED.value
        assert "CONNECTION_ERROR" in result.failure_codes or "HTTP_ERROR" in result.failure_codes
