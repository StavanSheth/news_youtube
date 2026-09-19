"""Tests for 236 micro-topic theme coverage and bidirectional integrity."""

from __future__ import annotations

import json
from pathlib import Path
from intelligence.config import load_config
from intelligence.themes.coverage import ThemeCoverageValidator

ROOT = Path(__file__).resolve().parent.parent.parent


def test_236_microtopic_theme_coverage_is_complete():
    matrix_path = ROOT / "config" / "microtopic_matrix.json"
    with matrix_path.open(encoding="utf-8-sig") as f:
        matrix_records = json.load(f)["records"]

    assert len(matrix_records) == 236

    app_config = load_config(ROOT)
    validator = ThemeCoverageValidator(matrix_records, app_config.themes)
    report = validator.validate_all()

    assert report["total_records"] == 236
    assert report["covered_count"] == 236
    assert report["uncovered_count"] == 0
    assert report["coverage_percentage"] == 100.0
    assert report["is_complete"] is True
    assert not report["failures"]


def test_bidirectional_mapping_no_orphans():
    matrix_path = ROOT / "config" / "microtopic_matrix.json"
    with matrix_path.open(encoding="utf-8-sig") as f:
        matrix_records = json.load(f)["records"]

    app_config = load_config(ROOT)
    validator = ThemeCoverageValidator(matrix_records, app_config.themes)
    uncovered, orphans = validator.check_bidirectional()

    assert not uncovered, f"Uncovered topics: {uncovered}"
    assert not orphans, f"Orphan themes: {orphans}"


def test_no_duplicate_theme_ids():
    matrix_path = ROOT / "config" / "microtopic_matrix.json"
    with matrix_path.open(encoding="utf-8-sig") as f:
        matrix_records = json.load(f)["records"]

    app_config = load_config(ROOT)
    validator = ThemeCoverageValidator(matrix_records, app_config.themes)
    duplicates = validator.check_duplicate_ids()

    assert not duplicates, f"Duplicate theme IDs found: {duplicates}"
