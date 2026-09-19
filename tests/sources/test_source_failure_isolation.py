"""Tests for failure isolation: single source failures do not abort the edition run."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml

from intelligence.source_validation import SourceAcceptanceEngine, validate_source_registry
from intelligence.sources import ProductionSourceRegistry


def _make_source(sid: str, enabled: bool = True, valid_url: bool = True) -> dict[str, Any]:
    return {
        "id": sid,
        "name": f"Source {sid}",
        "type": "rss",
        "role": "NEWS",
        "trust_tier": 2,
        "region": "global",
        "country": "GLOBAL",
        "domains": ["technology"],
        "topics": ["artificial-intelligence"],
        "micro_topics": [],
        "collection_method": "rss",
        "feed_url": "https://example.test/feed.rss" if valid_url else "",
        "enabled": enabled,
        "license_status": "PERMITTED",
        "retention_policy": "REQUIRED",
    }


_RSS_CONTENT = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Feed</title><link>https://example.test</link>
<item><title>Story</title><link>https://example.test/s1</link>
<description>Body text.</description></item></channel></rss>"""


class MockResponse:
    content = _RSS_CONTENT
    def raise_for_status(self): pass


class TestSourceFailureIsolation:
    def test_single_source_failure_does_not_prevent_other_sources_from_being_evaluated(self):
        """validate_source_registry must evaluate ALL sources, not abort on first failure."""
        sources = [
            _make_source("good-source"),
            _make_source("bad-source", valid_url=False),
        ]
        with patch("intelligence.source_validation.requests.get") as mock_get:
            mock_get.return_value = MockResponse()
            report = validate_source_registry(sources)

        assert "good-source" in report
        assert "bad-source" in report

    def test_disabled_source_does_not_prevent_evaluation_of_others(self):
        sources = [
            _make_source("enabled-source"),
            _make_source("disabled-source", enabled=False),
        ]
        with patch("intelligence.source_validation.requests.get") as mock_get:
            mock_get.return_value = MockResponse()
            report = validate_source_registry(sources)

        assert "enabled-source" in report
        assert "disabled-source" in report

    def test_network_error_on_one_source_isolated_to_that_source(self):
        import requests as req

        _RSS = _RSS_CONTENT

        def selective_get(url, timeout, headers):
            if "bad" in url:
                raise req.ConnectionError("refused")
            return MockResponse()

        sources = [
            _make_source("good-s"),
            {**_make_source("bad-s"), "feed_url": "https://bad.example.test/feed"},
        ]
        with patch("intelligence.source_validation.requests.get", side_effect=selective_get):
            report = validate_source_registry(sources)

        assert report["good-s"]["acceptance_status"] in {"READY", "QUARANTINED"}
        assert report["bad-s"]["acceptance_status"] == "QUARANTINED"
        assert any("NETWORK_ERROR" in fc for fc in report["bad-s"]["failure_codes"])

    def test_failure_codes_are_per_source(self):
        """Each source report must contain its own failure codes, not accumulate across sources."""
        sources = [
            _make_source("license-bad", valid_url=True),  # license invalid
            _make_source("url-bad", valid_url=False),       # url invalid
        ]
        sources[0]["license_status"] = "INVALID_LICENSE"

        with patch("intelligence.source_validation.requests.get") as mock_get:
            mock_get.return_value = MockResponse()
            report = validate_source_registry(sources)

        license_codes = report["license-bad"]["failure_codes"]
        url_codes = report["url-bad"]["failure_codes"]

        assert any("LICENSE" in fc for fc in license_codes)
        assert not any("LICENSE" in fc for fc in url_codes)

    def test_all_sources_get_latency_recorded_independently(self):
        sources = [
            _make_source("s1"),
            _make_source("s2"),
            _make_source("s3", valid_url=False),
        ]
        with patch("intelligence.source_validation.requests.get") as mock_get:
            mock_get.return_value = MockResponse()
            report = validate_source_registry(sources)

        for sid in ("s1", "s2", "s3"):
            assert "latency_ms" in report[sid]
            assert isinstance(report[sid]["latency_ms"], (int, float))

    def test_registry_ready_sources_excludes_quarantined_after_batch_evaluation(self, tmp_path: Path):
        """After batch evaluation, only fully-passing sources appear in ready_sources()."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "source_registry.yaml").write_text(yaml.dump({"sources": [
            _make_source("ready-s"),
            _make_source("quarantine-s", valid_url=False),
        ]}))

        reg = ProductionSourceRegistry.load_from_config(config_dir)
        engine = SourceAcceptanceEngine()

        with patch("intelligence.source_validation.requests.get") as mock_get:
            mock_get.return_value = MockResponse()
            results = {s.id: engine.evaluate_source(s) for s in reg.enabled_sources()}

        reg.update_acceptance(results)
        ready = [s.id for s in reg.ready_sources()]
        # quarantine-s must NOT be in ready
        assert "quarantine-s" not in ready
