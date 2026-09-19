"""Tests for source quarantine: QUARANTINED classification and explicit failure codes."""
from __future__ import annotations

from unittest.mock import patch


from intelligence.source_validation import SourceAcceptanceEngine
from intelligence.sources import SourceAcceptanceStatus


def _make_source(**overrides) -> dict:
    base = {
        "id": "quarantine-test",
        "name": "Quarantine Test",
        "type": "rss",
        "role": "NEWS",
        "trust_tier": 2,
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


class TestSourceQuarantine:
    def test_missing_url_produces_quarantine(self):
        engine = SourceAcceptanceEngine()
        result = engine.evaluate_source(_make_source(feed_url=""))
        assert result.is_quarantined

    def test_invalid_url_scheme_produces_quarantine(self):
        engine = SourceAcceptanceEngine()
        result = engine.evaluate_source(_make_source(feed_url="ftp://not-http.com/feed"))
        assert result.is_quarantined

    def test_missing_credential_produces_quarantine_with_code(self, monkeypatch):
        monkeypatch.delenv("TOTALLY_MISSING_KEY", raising=False)
        engine = SourceAcceptanceEngine()
        result = engine.evaluate_source(_make_source(
            authentication_required=True,
            authentication_env_var="TOTALLY_MISSING_KEY",
        ))
        assert result.is_quarantined
        assert any("MISSING_CREDENTIAL" in fc for fc in result.failure_codes)

    def test_network_error_produces_quarantine(self):
        import requests as req
        with patch("intelligence.source_validation.requests.get", side_effect=req.ConnectionError("refused")):
            engine = SourceAcceptanceEngine()
            result = engine.evaluate_source(_make_source())
        assert result.is_quarantined
        assert any("NETWORK_ERROR" in fc for fc in result.failure_codes)

    def test_license_failure_produces_quarantine(self):
        engine = SourceAcceptanceEngine()
        result = engine.evaluate_source(_make_source(license_status="INVALID"))
        assert result.is_quarantined
        assert "LICENSE_TERMS_UNRESOLVED" in result.failure_codes

    def test_retention_failure_produces_quarantine(self):
        engine = SourceAcceptanceEngine()
        result = engine.evaluate_source(_make_source(retention_policy="BOGUS"))
        assert result.is_quarantined
        assert "RETENTION_POLICY_UNRESOLVED" in result.failure_codes

    def test_quarantine_result_is_not_ready(self):
        engine = SourceAcceptanceEngine()
        result = engine.evaluate_source(_make_source(feed_url=""))
        assert not result.is_ready

    def test_quarantine_result_is_not_disabled(self):
        engine = SourceAcceptanceEngine()
        result = engine.evaluate_source(_make_source(feed_url=""))
        assert not result.is_disabled

    def test_failure_codes_are_non_empty_for_quarantine(self):
        engine = SourceAcceptanceEngine()
        result = engine.evaluate_source(_make_source(feed_url=""))
        assert len(result.failure_codes) > 0

    def test_disabled_source_does_not_produce_quarantine(self):
        engine = SourceAcceptanceEngine()
        result = engine.evaluate_source(_make_source(enabled=False))
        assert result.is_disabled
        assert not result.is_quarantined

    def test_quarantined_source_is_blocked_from_ready_view(self, tmp_path):
        import yaml
        from intelligence.sources import ProductionSourceRegistry, SourceAcceptanceResult

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "source_registry.yaml").write_text(yaml.dump({"sources": [_make_source()]}))
        reg = ProductionSourceRegistry.load_from_config(config_dir)

        # Simulate quarantine acceptance result
        q_result = SourceAcceptanceResult(
            source_id="quarantine-test",
            run_id="test",
            checked_at="2026-01-01T00:00:00+00:00",
            configured=True,
            reachable=False,
            authenticated=True,
            collection_success=False,
            response_valid=False,
            freshness_valid=False,
            schema_valid=False,
            content_extractable=False,
            role_valid=True,
            mapping_valid=True,
            evidence_valid=False,
            license_valid=True,
            retention_valid=True,
            status=SourceAcceptanceStatus.QUARANTINED.value,
            failure_codes=["NETWORK_ERROR"],
        )
        reg.update_acceptance({"quarantine-test": q_result})
        assert reg.ready_sources() == []
        assert len(reg.quarantined_sources()) == 1
