"""Tests for source license compliance, retention policies, and micro-topic source matrix."""

from __future__ import annotations

from pathlib import Path
import yaml

from intelligence.sources import ComplianceErrorCode, ProductionSourceRegistry, SourceContract

ROOT = Path(__file__).resolve().parents[2]


def test_source_compliance_validation():
    # Valid source
    valid_source = SourceContract(
        id="src-1",
        name="Valid Source",
        type="rss",
        role="NEWS",
        trust_tier=1,
        region="global",
        country="GLOBAL",
        domains=("tech",),
        topics=("ai",),
        micro_topics=("foundation-models",),
        collection_method="rss",
        url="https://example.com/rss",
        license_status="PERMITTED",
        retention_policy="REQUIRED",
        storage_permission=True,
    )
    ok, errors = valid_source.validate_compliance()
    assert ok
    assert len(errors) == 0

    # Non-compliant source (unknown license, storage forbidden)
    bad_source = SourceContract(
        id="src-bad",
        name="Bad Source",
        type="rss",
        role="NEWS",
        trust_tier=3,
        region="global",
        country="GLOBAL",
        domains=("tech",),
        topics=("ai",),
        micro_topics=("foundation-models",),
        collection_method="rss",
        url="https://example.com/rss",
        license_status="LICENSE_UNKNOWN",
        retention_policy="RETENTION_UNDEFINED",
        storage_permission=False,
    )
    bad_ok, bad_errors = bad_source.validate_compliance()
    assert not bad_ok
    assert ComplianceErrorCode.LICENSE_UNKNOWN.value in bad_errors
    assert ComplianceErrorCode.RETENTION_UNDEFINED.value in bad_errors
    assert ComplianceErrorCode.STORAGE_NOT_PERMITTED.value in bad_errors


def test_all_configured_sources_have_valid_compliance_policies():
    registry = ProductionSourceRegistry.load_from_config(ROOT / "config")
    sources = registry.all_sources()
    assert len(sources) >= 40

    for s in sources:
        ok, errors = s.validate_compliance()
        assert ok, f"Source {s.id} failed compliance: {errors}"


def test_source_microtopic_matrix_structure():
    matrix_file = ROOT / "config" / "source_microtopic_matrix.yaml"
    assert matrix_file.is_file()

    data = yaml.safe_load(matrix_file.read_text(encoding="utf-8"))
    assert data.get("total_microtopics") == 236
    mappings = data.get("mappings", {})
    assert len(mappings) == 236

    for key, val in mappings.items():
        assert "micro_topic_id" in val
        assert "domain" in val
        assert "primary_sources" in val
        assert "secondary_sources" in val
        assert "fallback_sources" in val
        assert "source_gaps" in val
