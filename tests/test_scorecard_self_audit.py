"""Self-audit test for scorecard integrity and zero hardcoded scores (Section 52).

Verifies that the scorecard evaluation architecture does not contain fake or hardcoded
measured score constants (e.g. `phase_2_scores['...'] = 95.0`), and that every score
is mathematically derived from executable check item ratios and evidence.
"""

from __future__ import annotations

from pathlib import Path
import re
import pytest

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from intelligence.quality.score import CheckItem, compute_category_score  # noqa: E402
from scripts.scorecard import evaluate_scorecard  # noqa: E402


def test_scorecard_source_has_zero_hardcoded_category_assignments():
    """Verify scripts/scorecard.py contains zero static score assignments to categories."""
    scorecard_path = ROOT / "scripts" / "scorecard.py"
    source = scorecard_path.read_text(encoding="utf-8")

    # Regex search for patterns like `phase_2_scores["..."] = 95.0` or `scores[...] = 96.0`
    suspicious_patterns = [
        r'phase_2_scores\[.*?\]\s*=\s*\d{2}(?:\.\d+)?',
        r'phase_3_scores\[.*?\]\s*=\s*\d{2}(?:\.\d+)?',
        r'scores\[.*?\]\s*=\s*9[0-9](?:\.[0-9]+)?',
    ]

    for pattern in suspicious_patterns:
        matches = re.findall(pattern, source)
        assert not matches, f"Detected suspicious hardcoded score assignment in scorecard.py: {matches}"


def test_score_calculation_is_strictly_evidence_ratio():
    """Verify compute_category_score calculates exact passed_weight / total_weight * 100."""
    checks = [
        CheckItem("check_1", 40.0, True),
        CheckItem("check_2", 30.0, True),
        CheckItem("check_3", 30.0, False),
    ]
    res = compute_category_score("Test Cat", checks)
    assert res.score == 70.0
    assert res.status == "FAIL"  # 70 < 90
    assert res.tests_passed == 2
    assert res.tests_total == 3

    # All pass
    checks_pass = [
        CheckItem("check_1", 50.0, True),
        CheckItem("check_2", 50.0, True),
    ]
    res_pass = compute_category_score("Pass Cat", checks_pass)
    assert res_pass.score == 100.0
    assert res_pass.status == "PASS"


def test_blocking_check_failure_blocks_category():
    """Verify blocking check failure marks category as FAIL even if weight is high."""
    checks = [
        CheckItem("minor_check_1", 50.0, True),
        CheckItem("minor_check_2", 45.0, True),
        CheckItem("critical_check", 5.0, False, blocking=True),
    ]
    res = compute_category_score("Blocked Cat", checks)
    assert res.score <= 59.0
    assert res.status == "FAIL"
    assert "critical_check" in res.blocking_failures


def test_evaluate_scorecard_produces_fully_derived_evidence():
    """Verify evaluate_scorecard returns complete evidence tree without arbitrary constants."""
    data = evaluate_scorecard(root=ROOT)
    assert data["overall"]["status"] in ("PASS", "FAIL")
    assert isinstance(data["overall"]["score"], float)

    # Check that all 12 Phase 2 categories exist and have check evidence
    p2_details = data["phase_2"]["details"]
    assert len(p2_details) == 12
    for cat_name, cat_data in p2_details.items():
        assert "score" in cat_data
        assert "evidence" in cat_data
        assert len(cat_data["evidence"]) >= 2
        # Verify evidence weights sum to 100
        total_weight = sum(ev["weight"] for ev in cat_data["evidence"])
        assert total_weight == pytest.approx(100.0, abs=0.1), f"Category {cat_name} weights do not sum to 100: {total_weight}"

    # Check that all 15 Phase 3 categories exist and have check evidence
    p3_details = data["phase_3"]["details"]
    assert len(p3_details) == 15
    for cat_name, cat_data in p3_details.items():
        assert "score" in cat_data
        assert "evidence" in cat_data
        assert len(cat_data["evidence"]) >= 2
        total_weight = sum(ev["weight"] for ev in cat_data["evidence"])
        assert total_weight == pytest.approx(100.0, abs=0.1), f"Category {cat_name} weights do not sum to 100: {total_weight}"
