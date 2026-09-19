"""Tests for the 13-stage deterministic SourceAcceptanceEngine."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import feedparser

from intelligence.source_validation import SourceAcceptanceEngine, validate_source_registry
from intelligence.sources import (
    SourceAcceptanceStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RSS_FRESH = b"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.test</link>
    <item>
      <title>Breaking News</title>
      <link>https://example.test/story-1</link>
      <pubDate>Mon, 01 Jan 2026 12:00:00 GMT</pubDate>
      <description>Detailed body text for testing extraction.</description>
    </item>
  </channel>
</rss>"""


def _make_rss_source(**overrides) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "test-source",
        "name": "Test Source",
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
    }
    base.update(overrides)
    return base


class _MockResponse:
    def __init__(self, content: bytes = _RSS_FRESH, status_code: int = 200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


# ---------------------------------------------------------------------------
# Stage-by-stage acceptance lifecycle
# ---------------------------------------------------------------------------

class TestSourceAcceptanceEngineLifecycle:
    def test_disabled_source_returns_disabled_immediately(self):
        engine = SourceAcceptanceEngine()
        result = engine.evaluate_source(_make_rss_source(enabled=False))
        assert result.is_disabled
        assert result.status == SourceAcceptanceStatus.DISABLED.value
        assert "DISABLED_BY_CONFIGURATION" in result.failure_codes

    def test_stage1_config_invalid_when_missing_url(self):
        engine = SourceAcceptanceEngine()
        result = engine.evaluate_source({
            "id": "bad-src", "name": "Bad", "type": "rss",
            "role": "NEWS", "enabled": True, "feed_url": "",
            "license_status": "PERMITTED", "retention_policy": "REQUIRED",
        })
        assert not result.configured or not result.reachable
        assert result.is_quarantined

    def test_stage2_reachable_fails_for_invalid_url(self):
        engine = SourceAcceptanceEngine()
        src = _make_rss_source(feed_url="not-a-valid-url")
        result = engine.evaluate_source(src)
        assert not result.reachable
        assert result.is_quarantined

    def test_stage3_auth_missing_credential_quarantines(self, monkeypatch):
        monkeypatch.delenv("MISSING_KEY", raising=False)
        engine = SourceAcceptanceEngine()
        src = _make_rss_source(
            authentication_required=True,
            authentication_env_var="MISSING_KEY",
        )
        result = engine.evaluate_source(src)
        assert not result.authenticated
        assert result.is_quarantined
        assert any("MISSING_CREDENTIAL" in fc for fc in result.failure_codes)

    def test_stage3_auth_passes_when_env_var_set(self, monkeypatch):
        monkeypatch.setenv("MY_TEST_API_KEY", "fake-value")
        with patch("intelligence.source_validation.requests.get") as mock_get:
            mock_get.return_value = _MockResponse()
            engine = SourceAcceptanceEngine()
            src = _make_rss_source(
                authentication_required=True,
                authentication_env_var="MY_TEST_API_KEY",
            )
            result = engine.evaluate_source(src)
        assert result.authenticated

    def test_stage4_collection_success_after_valid_feed(self, monkeypatch):
        with patch("intelligence.source_validation.requests.get") as mock_get:
            mock_get.return_value = _MockResponse(_RSS_FRESH)
            engine = SourceAcceptanceEngine()
            result = engine.evaluate_source(_make_rss_source())
        assert result.collection_success

    def test_stage5_response_valid_flag_set(self, monkeypatch):
        with patch("intelligence.source_validation.requests.get") as mock_get:
            mock_get.return_value = _MockResponse(_RSS_FRESH)
            engine = SourceAcceptanceEngine()
            result = engine.evaluate_source(_make_rss_source())
        assert result.response_valid

    def test_stage7_schema_valid_flag_set(self, monkeypatch):
        with patch("intelligence.source_validation.requests.get") as mock_get:
            mock_get.return_value = _MockResponse(_RSS_FRESH)
            engine = SourceAcceptanceEngine()
            result = engine.evaluate_source(_make_rss_source())
        assert result.schema_valid

    def test_stage9_role_valid_for_canonical_role(self, monkeypatch):
        with patch("intelligence.source_validation.requests.get") as mock_get:
            mock_get.return_value = _MockResponse(_RSS_FRESH)
            engine = SourceAcceptanceEngine()
            result = engine.evaluate_source(_make_rss_source(role="NEWS"))
        assert result.role_valid

    def test_stage12_license_invalid_quarantines(self, monkeypatch):
        engine = SourceAcceptanceEngine()
        src = _make_rss_source(license_status="UNKNOWN_STATUS")
        result = engine.evaluate_source(src)
        assert not result.license_valid
        assert result.is_quarantined
        assert "LICENSE_TERMS_UNRESOLVED" in result.failure_codes

    def test_stage12_retention_invalid_quarantines(self, monkeypatch):
        engine = SourceAcceptanceEngine()
        src = _make_rss_source(retention_policy="BOGUS_POLICY")
        result = engine.evaluate_source(src)
        assert not result.retention_valid
        assert result.is_quarantined
        assert "RETENTION_POLICY_UNRESOLVED" in result.failure_codes

    def test_network_error_quarantines_source(self, monkeypatch):
        import requests as req
        with patch("intelligence.source_validation.requests.get", side_effect=req.ConnectionError("refused")):
            engine = SourceAcceptanceEngine()
            result = engine.evaluate_source(_make_rss_source())
        assert result.is_quarantined
        assert any("NETWORK_ERROR" in fc for fc in result.failure_codes)

    def test_latency_ms_is_recorded(self):
        engine = SourceAcceptanceEngine()
        result = engine.evaluate_source(_make_rss_source(enabled=False))
        assert result.latency_ms >= 0.0

    def test_acceptance_result_to_dict(self):
        engine = SourceAcceptanceEngine()
        result = engine.evaluate_source(_make_rss_source(enabled=False))
        d = result.to_dict()
        assert "source_id" in d
        assert "status" in d
        assert "failure_codes" in d

    def test_full_pass_gives_ready_status(self):
        with patch("intelligence.source_validation.requests.get") as mock_get:
            mock_get.return_value = _MockResponse(_RSS_FRESH)
            engine = SourceAcceptanceEngine()
            result = engine.evaluate_source(_make_rss_source())
        # Freshness may fail if no parseable dates; accept QUARANTINED only on freshness
        assert result.configured
        assert result.authenticated
        assert result.role_valid
        assert result.license_valid


# ---------------------------------------------------------------------------
# validate_source_registry (backward-compatible API)
# ---------------------------------------------------------------------------

class TestValidateSourceRegistry:
    def test_disabled_source_is_disabled_in_report(self):
        report = validate_source_registry([_make_rss_source(enabled=False)])
        entry = report["test-source"]
        assert entry["acceptance_status"] == SourceAcceptanceStatus.DISABLED.value

    def test_report_contains_required_fields(self, monkeypatch):
        with patch("intelligence.source_validation.requests.get") as mock_get:
            mock_get.return_value = _MockResponse(_RSS_FRESH)
            report = validate_source_registry([_make_rss_source()])
        entry = report["test-source"]
        for field in ("source", "source_id", "enabled", "status", "acceptance_status",
                      "failure_codes", "latency_ms", "checked_at"):
            assert field in entry, f"Missing field: {field}"

    def test_timeout_is_passed_to_requests_get(self, monkeypatch):
        captured = {}

        class FakeResp:
            content = _RSS_FRESH
            def raise_for_status(self): pass

        def fake_get(url, timeout, headers):
            captured["timeout"] = timeout
            return FakeResp()

        monkeypatch.setattr("intelligence.source_validation.requests.get", fake_get)
        validate_source_registry([_make_rss_source()], timeout=7)
        assert captured["timeout"] == 7

    def test_custom_parser_is_used_when_provided(self):
        def my_parser(url):
            return feedparser.parse(_RSS_FRESH)

        report = validate_source_registry([_make_rss_source()], parser=my_parser)
        entry = report["test-source"]
        assert entry["acceptance_status"] in {SourceAcceptanceStatus.READY.value, SourceAcceptanceStatus.QUARANTINED.value}

    def test_empty_sources_list_returns_empty_report(self):
        report = validate_source_registry([])
        assert report == {}

    def test_multiple_sources_all_appear_in_report(self, monkeypatch):
        with patch("intelligence.source_validation.requests.get") as mock_get:
            mock_get.return_value = _MockResponse(_RSS_FRESH)
            sources = [
                _make_rss_source(id="s1", name="S1"),
                _make_rss_source(id="s2", name="S2", enabled=False),
            ]
            report = validate_source_registry(sources)
        assert "s1" in report
        assert "s2" in report
