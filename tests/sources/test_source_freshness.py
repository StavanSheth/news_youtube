"""Tests for FreshnessPolicy evaluation and stale content detection."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch


from intelligence.source_validation import SourceAcceptanceEngine
from intelligence.sources import FreshnessPolicy


def _make_rss_with_age(age_hours: float) -> bytes:
    """Build an RSS feed with a single item published `age_hours` ago."""
    pub_time = datetime.now(UTC) - timedelta(hours=age_hours)
    pub_date = pub_time.strftime("%a, %d %b %Y %H:%M:%S GMT")
    return (
        f'<?xml version="1.0"?>'
        f'<rss version="2.0"><channel><title>Feed</title><link>https://example.test</link>'
        f'<item>'
        f'<title>Fresh story</title>'
        f'<link>https://example.test/story</link>'
        f'<pubDate>{pub_date}</pubDate>'
        f'<description>Content body.</description>'
        f'</item></channel></rss>'
    ).encode()


def _make_source(**overrides) -> dict:
    base = {
        "id": "freshness-test",
        "name": "Freshness Test",
        "type": "rss",
        "role": "NEWS",
        "trust_tier": 1,
        "region": "global",
        "country": "GLOBAL",
        "domains": ["technology"],
        "topics": ["artificial-intelligence"],
        "micro_topics": [],
        "collection_method": "rss",
        "feed_url": "https://example.test/feed.rss",
        "enabled": True,
        "license_status": "PERMITTED",
        "retention_policy": "REQUIRED",
        "freshness_policy": {
            "max_age_hours": 24,
            "stale_after_hours": 48,
            "schedule": "daily",
        },
    }
    base.update(overrides)
    return base


class MockResponse:
    def __init__(self, content: bytes):
        self.content = content
    def raise_for_status(self): pass


class TestFreshnessValidation:
    def test_fresh_content_within_window_passes(self):
        fresh_feed = _make_rss_with_age(12.0)  # 12h old, window=48h
        with patch("intelligence.source_validation.requests.get") as mock_get:
            mock_get.return_value = MockResponse(fresh_feed)
            engine = SourceAcceptanceEngine()
            result = engine.evaluate_source(_make_source())
        assert result.freshness_valid

    def test_stale_content_beyond_window_fails(self):
        stale_feed = _make_rss_with_age(96.0)  # 96h old, window=48h
        with patch("intelligence.source_validation.requests.get") as mock_get:
            mock_get.return_value = MockResponse(stale_feed)
            engine = SourceAcceptanceEngine()
            result = engine.evaluate_source(_make_source())
        assert not result.freshness_valid
        assert result.is_quarantined

    def test_stale_failure_code_includes_age(self):
        stale_feed = _make_rss_with_age(100.0)
        with patch("intelligence.source_validation.requests.get") as mock_get:
            mock_get.return_value = MockResponse(stale_feed)
            engine = SourceAcceptanceEngine()
            result = engine.evaluate_source(_make_source())
        assert any("STALE_CONTENT" in fc for fc in result.failure_codes)

    def test_no_dates_in_feed_warns_but_not_stale(self):
        no_date_feed = (
            b'<?xml version="1.0"?><rss version="2.0"><channel><title>Feed</title>'
            b'<link>https://example.test</link>'
            b'<item><title>No Date</title><link>https://example.test/nd</link>'
            b'<description>body</description></item></channel></rss>'
        )
        with patch("intelligence.source_validation.requests.get") as mock_get:
            mock_get.return_value = MockResponse(no_date_feed)
            engine = SourceAcceptanceEngine()
            result = engine.evaluate_source(_make_source())
        # No dates → not provably stale → freshness_valid=True with a warning
        assert result.freshness_valid
        assert any("NO_PARSEABLE_PUBLICATION_DATES" in w for w in result.warnings)

    def test_freshness_policy_from_mapping_defaults(self):
        fp = FreshnessPolicy.from_mapping(None)
        assert fp.max_age_hours == 48
        assert fp.stale_after_hours == 72

    def test_freshness_policy_stale_after_shorter_than_max_is_valid(self):
        fp = FreshnessPolicy(max_age_hours=12, stale_after_hours=6)
        assert fp.max_age_hours == 12
        assert fp.stale_after_hours == 6

    def test_latest_content_at_populated_for_dated_feed(self):
        fresh_feed = _make_rss_with_age(2.0)
        with patch("intelligence.source_validation.requests.get") as mock_get:
            mock_get.return_value = MockResponse(fresh_feed)
            engine = SourceAcceptanceEngine()
            result = engine.evaluate_source(_make_source())
        assert result.latest_content_at is not None
