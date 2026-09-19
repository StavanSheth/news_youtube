"""Tests for production hardening, runtime config validation, and operations source acceptance."""

from __future__ import annotations

from pathlib import Path

from intelligence.config import validate_runtime_production_config
from intelligence.operations.source_acceptance import run_source_acceptance

ROOT = Path(__file__).resolve().parents[2]


def test_production_runtime_configuration_validation():
    diag = validate_runtime_production_config(ROOT)
    assert diag["valid"], f"Production configuration validation failed: {diag['errors']}"
    assert len(diag["errors"]) == 0


def test_operations_source_acceptance_run():
    report = run_source_acceptance(live=False, config_dir=ROOT / "config")
    assert report["sources_checked"] >= 40
    dims = report["dimensions"]
    assert dims["authentication"] == "PASS"
    assert dims["reachability"] == "PASS"
    assert dims["collection"] == "PASS"
    assert dims["freshness"] == "PASS"
    assert dims["schema"] == "PASS"
    assert dims["content_extraction"] == "PASS"
    assert dims["license"] == "PASS"
    assert dims["retention"] == "PASS"
    assert dims["microtopic_mapping"] == "PASS"
    assert dims["rag_ingestion"] == "PASS"
