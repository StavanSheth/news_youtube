"""Tests for ProductionSourceRegistry — loading, dedup, enabled/ready/quarantined views."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from intelligence.sources import (
    ProductionSourceRegistry,
    SourceAcceptanceResult,
    SourceAcceptanceStatus,
    SourceRole,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_registry_yaml(sources: list[dict]) -> str:
    return yaml.dump({"sources": sources})


def _base_source(**overrides) -> dict:
    base = {
        "id": "test-rss-1",
        "name": "Test RSS 1",
        "type": "rss",
        "role": "NEWS",
        "trust_tier": 2,
        "region": "global",
        "country": "GLOBAL",
        "domains": ["technology"],
        "topics": ["artificial-intelligence"],
        "micro_topics": ["foundation-models"],
        "collection_method": "rss",
        "feed_url": "https://example.com/feed.rss",
        "enabled": True,
        "license_status": "PERMITTED",
        "retention_policy": "REQUIRED",
    }
    base.update(overrides)
    return base


def _write_registry(tmp_path: Path, sources: list[dict]) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "source_registry.yaml").write_text(yaml.dump({"sources": sources}))
    return config_dir


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------

class TestProductionSourceRegistryLoading:
    def test_load_empty_registry(self, tmp_path: Path):
        config_dir = _write_registry(tmp_path, [])
        reg = ProductionSourceRegistry.load_from_config(config_dir)
        assert reg.all_sources() == []

    def test_load_single_rss_source(self, tmp_path: Path):
        config_dir = _write_registry(tmp_path, [_base_source()])
        reg = ProductionSourceRegistry.load_from_config(config_dir)
        sources = reg.all_sources()
        assert len(sources) == 1
        assert sources[0].id == "test-rss-1"
        assert sources[0].role == SourceRole.NEWS

    def test_load_multiple_sources(self, tmp_path: Path):
        config_dir = _write_registry(tmp_path, [
            _base_source(id="s1"),
            _base_source(id="s2"),
            _base_source(id="s3"),
        ])
        reg = ProductionSourceRegistry.load_from_config(config_dir)
        assert len(reg.all_sources()) == 3

    def test_duplicate_source_id_raises(self, tmp_path: Path):
        with pytest.raises(ValueError, match="Duplicate source_id"):
            config_dir = _write_registry(tmp_path, [
                _base_source(id="dup"),
                _base_source(id="dup"),
            ])
            ProductionSourceRegistry.load_from_config(config_dir)

    def test_load_youtube_channel_from_channels_yaml(self, tmp_path: Path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "source_registry.yaml").write_text(yaml.dump({"sources": []}))
        (config_dir / "channels.yaml").write_text(yaml.dump({
            "channels": [{
                "id": "UCtest123",
                "name": "AI Channel",
                "enabled": True,
                "trust_tier": 2,
                "region": "global",
                "country": "GLOBAL",
                "domains": ["artificial-intelligence"],
                "topics": ["foundation-models"],
            }]
        }))
        reg = ProductionSourceRegistry.load_from_config(config_dir)
        sources = reg.all_sources()
        assert any(s.id == "UCtest123" for s in sources)
        yt_source = next(s for s in sources if s.id == "UCtest123")
        assert yt_source.type == "youtube"
        assert yt_source.role == SourceRole.VIDEO

    def test_missing_config_dir_yields_empty_registry(self, tmp_path: Path):
        non_existent = tmp_path / "does_not_exist"
        reg = ProductionSourceRegistry.load_from_config(non_existent)
        assert reg.all_sources() == []


# ---------------------------------------------------------------------------
# enabled_sources / ready_sources / quarantined_sources views
# ---------------------------------------------------------------------------

class TestRegistryViews:
    def _reg_with_acceptance(self, tmp_path: Path):
        config_dir = _write_registry(tmp_path, [
            _base_source(id="s-enabled", enabled=True),
            _base_source(id="s-disabled", enabled=False),
        ])
        reg = ProductionSourceRegistry.load_from_config(config_dir)
        return reg

    def test_enabled_sources_filters_correctly(self, tmp_path: Path):
        reg = self._reg_with_acceptance(tmp_path)
        enabled = reg.enabled_sources()
        assert len(enabled) == 1
        assert enabled[0].id == "s-enabled"

    def test_ready_sources_empty_before_acceptance(self, tmp_path: Path):
        reg = self._reg_with_acceptance(tmp_path)
        assert reg.ready_sources() == []

    def test_quarantined_sources_empty_before_acceptance(self, tmp_path: Path):
        reg = self._reg_with_acceptance(tmp_path)
        assert reg.quarantined_sources() == []

    def _make_acceptance(self, source_id: str, status: str) -> SourceAcceptanceResult:
        return SourceAcceptanceResult(
            source_id=source_id,
            run_id="test",
            checked_at="2026-01-01T00:00:00+00:00",
            configured=True,
            reachable=True,
            authenticated=True,
            collection_success=True,
            response_valid=True,
            freshness_valid=True,
            schema_valid=True,
            content_extractable=True,
            role_valid=True,
            mapping_valid=True,
            evidence_valid=True,
            license_valid=True,
            retention_valid=True,
            status=status,
        )

    def test_ready_sources_after_acceptance_update(self, tmp_path: Path):
        reg = self._reg_with_acceptance(tmp_path)
        reg.update_acceptance({
            "s-enabled": self._make_acceptance("s-enabled", SourceAcceptanceStatus.READY.value),
        })
        ready = reg.ready_sources()
        assert len(ready) == 1
        assert ready[0].id == "s-enabled"

    def test_quarantined_sources_after_acceptance_update(self, tmp_path: Path):
        reg = self._reg_with_acceptance(tmp_path)
        reg.update_acceptance({
            "s-enabled": self._make_acceptance("s-enabled", SourceAcceptanceStatus.QUARANTINED.value),
        })
        quarantined = reg.quarantined_sources()
        assert len(quarantined) == 1
        assert quarantined[0].id == "s-enabled"

    def test_get_acceptance_returns_none_before_evaluation(self, tmp_path: Path):
        reg = self._reg_with_acceptance(tmp_path)
        assert reg.get_acceptance("s-enabled") is None

    def test_get_acceptance_returns_result_after_update(self, tmp_path: Path):
        reg = self._reg_with_acceptance(tmp_path)
        result = self._make_acceptance("s-enabled", SourceAcceptanceStatus.READY.value)
        reg.update_acceptance({"s-enabled": result})
        assert reg.get_acceptance("s-enabled") is result

    def test_get_source_raises_for_unknown_id(self, tmp_path: Path):
        reg = self._reg_with_acceptance(tmp_path)
        with pytest.raises(KeyError, match="Source not found"):
            reg.get_source("nonexistent-id")
