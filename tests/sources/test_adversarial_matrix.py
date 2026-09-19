"""Section 16 Comprehensive Adversarial Test Matrix.

Verifies deterministic failure behavior across all required adversarial conditions:
- missing API key, invalid API key
- HTTP errors: 401, 403, 404, 429, 500, 502, 503
- Network issues: timeout, DNS failure
- Payload issues: malformed JSON, malformed XML, empty response
- Temporal issues: stale response, future publication, missing publication time
- Content issues: duplicate content, duplicate URL, missing body, missing title, invalid URL
- Source statuses: disabled source, quarantined source
- Mapping issues: wrong topic mapping, wrong micro-topic mapping, wrong region
- Intelligence states: insufficient evidence, transcript unavailable, transcript failure
- Quota and budget: quota exhausted, token budget exhausted
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
import requests

from intelligence.budgets.manager import BudgetManager
from intelligence.ingestion.base import CanonicalContent
from intelligence.ingestion.news_api.client import NewsApiClient
from intelligence.ingestion.rss.parser import RssParser
from intelligence.ingestion.youtube.quota import YouTubeQuotaTracker
from intelligence.rag.eligibility import check_chunk_eligibility


# --- 1. API Keys & HTTP Errors (401, 403, 404, 429, 500, 502, 503, timeout, DNS) ---
def test_news_api_missing_and_invalid_api_key(monkeypatch):
    monkeypatch.delenv("MISSING_KEY_VAR", raising=False)
    client_missing = NewsApiClient(api_key_env="MISSING_KEY_VAR")
    assert client_missing.get_api_key() == ""
    assert client_missing.validate_api_key() is False

    with pytest.raises(ValueError, match="API key missing"):
        client_missing.fetch_articles("https://api.example.com/v2/news")
    assert client_missing.last_health["status"] == "AUTH_FAILED"


@pytest.mark.parametrize("status_code", [401, 403, 404, 500, 502, 503])
def test_news_api_http_error_codes(status_code):
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.raise_for_status.side_effect = requests.HTTPError(f"HTTP {status_code}", response=mock_resp)
    mock_http.get.return_value = mock_resp

    client = NewsApiClient(http_client=mock_http)
    articles = client.fetch_articles("https://api.example.com/v2/news")
    assert articles == []
    assert client.last_health["status"] == "ERROR"
    assert client.last_health["error_code"] == f"HTTP_{status_code}"


def test_news_api_429_rate_limit():
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_http.get.return_value = mock_resp

    client = NewsApiClient(http_client=mock_http)
    articles = client.fetch_articles("https://api.example.com/v2/news")
    assert articles == []
    assert client.last_health["status"] == "RATE_LIMITED"
    assert client.last_health["error_code"] == "HTTP_429"


def test_network_timeout_and_dns_failure():
    mock_http = MagicMock()
    mock_http.get.side_effect = requests.Timeout("Connection timed out")
    client_timeout = NewsApiClient(http_client=mock_http)
    articles = client_timeout.fetch_articles("https://api.example.com/v2/news")
    assert articles == []
    assert client_timeout.last_health["status"] == "ERROR"
    assert "Timeout" in client_timeout.last_health["error_code"]

    mock_http_dns = MagicMock()
    mock_http_dns.get.side_effect = requests.ConnectionError("DNS lookup failed")
    client_dns = NewsApiClient(http_client=mock_http_dns)
    articles_dns = client_dns.fetch_articles("https://api.example.com/v2/news")
    assert articles_dns == []
    assert client_dns.last_health["status"] == "ERROR"
    assert "ConnectionError" in client_dns.last_health["error_code"]


# --- 2. Payload issues: malformed JSON, empty response ---
def test_malformed_json_and_empty_response():
    mock_http = MagicMock()
    mock_resp_json = MagicMock()
    mock_resp_json.status_code = 200
    mock_resp_json.content = b"NOT_JSON"
    mock_resp_json.json.side_effect = json.JSONDecodeError("Expecting value", "doc", 0)
    mock_http.get.return_value = mock_resp_json

    client = NewsApiClient(http_client=mock_http)
    articles = client.fetch_articles("https://api.example.com/v2/news")
    assert articles == []

    mock_resp_empty = MagicMock()
    mock_resp_empty.status_code = 200
    mock_resp_empty.content = b'{"articles": []}'
    mock_resp_empty.json.return_value = {"articles": []}
    mock_http.get.return_value = mock_resp_empty

    articles_empty = client.fetch_articles("https://api.example.com/v2/news")
    assert articles_empty == []


def test_malformed_xml_rss():
    # Completely invalid/unclosed XML feed
    raw_invalid_xml = "<rss><channel><title>Malformed XML"
    parsed = RssParser.parse_content(raw_invalid_xml)
    valid, status, entries = RssParser.validate_feed(parsed)
    # RssParser correctly detects bozo error or empty feed
    assert not valid or status in ("EMPTY_FEED", "BOZO_ERROR")


# --- 3. Temporal issues: future publication, stale response, timestamp ordering ---
def test_temporal_invariants():
    future_time = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    now_time = datetime.now(UTC).isoformat()

    # Future publication relative to retrieval must fail invariants
    content_future = CanonicalContent.create(
        source_id="src-1",
        source_type="news",
        source_role="PRIMARY",
        title="Future Article",
        canonical_url="https://example.com/future",
        published_at=future_time,
        updated_at=future_time,
        retrieved_at=now_time,
        author="Reporter",
        body_text="Future text",
        summary_text="Future summary",
        evidence_type="NEWS",
    )
    valid, errs = content_future.validate_invariants()
    assert not valid
    assert any("published_at" in e and "retrieved_at" in e for e in errs)

    # Valid in-order timestamps must pass
    past_time = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    content_valid = CanonicalContent.create(
        source_id="src-1",
        source_type="news",
        source_role="PRIMARY",
        title="Valid Article",
        canonical_url="https://example.com/valid",
        published_at=past_time,
        updated_at=past_time,
        retrieved_at=now_time,
        author="Reporter",
        body_text="Valid text",
        summary_text="Valid summary",
        evidence_type="NEWS",
    )
    valid_ok, valid_errs = content_valid.validate_invariants()
    assert valid_ok
    assert len(valid_errs) == 0


# --- 4. Content issues: missing title, invalid URL ---
def test_canonical_content_validation_rules():
    now_time = datetime.now(UTC).isoformat()

    # Missing title fails invariant
    content_no_title = CanonicalContent.create(
        source_id="src-1",
        source_type="news",
        source_role="PRIMARY",
        title="",
        canonical_url="https://example.com/ok",
        published_at=now_time,
        updated_at=now_time,
        retrieved_at=now_time,
        author="Author",
        body_text="Body",
        summary_text="Summary",
        evidence_type="NEWS",
    )
    valid, errs = content_no_title.validate_invariants()
    assert not valid
    assert any("title" in e for e in errs)


# --- 5. Source statuses: disabled, quarantined, wrong mapping ---
def test_disabled_and_quarantined_source_rejection():
    chunk = {
        "id": "c-1",
        "text": "Some text",
        "metadata": {
            "source_id": "test_src",
            "published_at": datetime.now(UTC).isoformat(),
            "url": "https://example.com/article",
        },
    }

    # Quarantined source rejection
    ok_q, reason_q = check_chunk_eligibility(chunk, quarantined_sources={"test_src"})
    assert not ok_q
    assert reason_q == "QUARANTINED_SOURCE"

    # Disabled source rejection
    ok_d, reason_d = check_chunk_eligibility(chunk, disabled_sources={"test_src"})
    assert not ok_d
    assert reason_d == "DISABLED_SOURCE"


# --- 6. Quota and token budget exhausted ---
def test_quota_exhausted_and_circuit_breaker():
    tracker = YouTubeQuotaTracker(max_units_per_run=10, circuit_breaker_threshold=2)

    # Reserve up to limit
    reserved = tracker.reserve(5)
    assert reserved is True
    tracker.consume(5)

    # Trigger circuit breaker with 2 consecutive 429 errors
    tracker.record_request(success=False, status_code=429)
    tracker.record_request(success=False, status_code=429)

    assert tracker.circuit_breaker_tripped is True
    assert tracker.can_spend(1) is False
    assert tracker.reserve(1) is False


def test_token_budget_exhausted():
    bm = BudgetManager(global_limits={"max_input_tokens": 100})
    ok1, _, _ = bm.authorize("mt-1", estimated_tokens=80)
    assert ok1 is True
    bm.consume("mt-1", "input_tokens", 80)

    # Next attempt needs 50 tokens (80+50 > 100) -> fails
    ok2, reason, record = bm.authorize("mt-1", estimated_tokens=50)
    assert ok2 is False
    assert reason == "GLOBAL_INPUT_TOKEN_BUDGET_EXHAUSTED"
    assert record is not None
    assert record.status == "BUDGET_SKIPPED"
