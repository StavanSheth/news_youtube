"""Tests for region/topic/domain mapping validation in SourceAcceptanceEngine."""
from __future__ import annotations

from intelligence.source_validation import SourceAcceptanceEngine


def _make_source(**overrides) -> dict:
    base = {
        "id": "mapping-test",
        "name": "Mapping Test",
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


def _taxonomy(**overrides) -> dict:
    """Build a minimal taxonomy for mapping validation tests."""
    base = {
        "domains": {
            "technology": {"topics": ["artificial-intelligence", "cloud-computing"]},
            "finance": {"topics": ["markets", "banking"]},
        },
        "regions": ["global", "us", "eu", "asia"],
        "countries": ["GLOBAL", "US", "GB", "DE"],
    }
    base.update(overrides)
    return base


class TestMappingValidation:
    def test_valid_region_passes(self):
        engine = SourceAcceptanceEngine(taxonomy=_taxonomy())
        result = engine.evaluate_source(_make_source(region="global", country="US", enabled=False))
        assert result.mapping_valid

    def test_invalid_region_fails(self):
        engine = SourceAcceptanceEngine(taxonomy=_taxonomy())
        result = engine.evaluate_source(_make_source(region="FAKE_REGION", enabled=False))
        assert not result.mapping_valid
        assert any("INVALID_REGION" in fc for fc in result.failure_codes)

    def test_invalid_country_fails(self):
        engine = SourceAcceptanceEngine(taxonomy=_taxonomy())
        result = engine.evaluate_source(_make_source(country="XX", enabled=False))
        assert not result.mapping_valid
        assert any("INVALID_COUNTRY" in fc for fc in result.failure_codes)

    def test_invalid_domain_fails(self):
        engine = SourceAcceptanceEngine(taxonomy=_taxonomy())
        result = engine.evaluate_source(
            _make_source(domains=["nonexistent-domain"], enabled=False)
        )
        assert not result.mapping_valid
        assert any("INVALID_DOMAIN" in fc for fc in result.failure_codes)

    def test_invalid_topic_fails(self):
        engine = SourceAcceptanceEngine(taxonomy=_taxonomy())
        result = engine.evaluate_source(
            _make_source(topics=["nonexistent-topic"], enabled=False)
        )
        assert not result.mapping_valid
        assert any("INVALID_TOPIC" in fc for fc in result.failure_codes)

    def test_valid_domain_and_topic_passes(self):
        engine = SourceAcceptanceEngine(taxonomy=_taxonomy())
        result = engine.evaluate_source(
            _make_source(domains=["technology"], topics=["artificial-intelligence"], enabled=False)
        )
        assert result.mapping_valid

    def test_empty_taxonomy_skips_validation(self):
        """If no taxonomy provided, mapping validation must not fail."""
        engine = SourceAcceptanceEngine(taxonomy={})
        result = engine.evaluate_source(_make_source(region="TOTALLY_RANDOM", enabled=False))
        assert result.mapping_valid

    def test_multiple_invalid_failures_accumulated(self):
        engine = SourceAcceptanceEngine(taxonomy=_taxonomy())
        result = engine.evaluate_source(
            _make_source(region="BAD_R", country="BAD_C", enabled=False)
        )
        region_failures = [fc for fc in result.failure_codes if "INVALID_REGION" in fc]
        country_failures = [fc for fc in result.failure_codes if "INVALID_COUNTRY" in fc]
        assert len(region_failures) >= 1
        assert len(country_failures) >= 1
