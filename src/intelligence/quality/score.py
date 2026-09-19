"""Authoritative scoring helpers and category result structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckItem:
    name: str
    weight: float
    passed: bool
    blocking: bool = False
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CategoryResult:
    category: str
    score: float
    status: str
    tests_total: int
    tests_passed: int
    tests_failed: int
    evidence: list[dict[str, Any]]
    blocking_failures: list[str]
    checks: list[CheckItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "score": round(self.score, 1),
            "status": self.status,
            "tests_total": self.tests_total,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "evidence": self.evidence,
            "blocking_failures": self.blocking_failures,
        }


def compute_category_score(
    category: str,
    checks: list[CheckItem],
    min_threshold: float = 90.0,
) -> CategoryResult:
    """Compute score as passed_weight / total_weight * 100 with blocking checks cap."""
    if not checks:
        return CategoryResult(
            category=category,
            score=0.0,
            status="FAIL",
            tests_total=0,
            tests_passed=0,
            tests_failed=0,
            evidence=[],
            blocking_failures=["NO_CHECKS_DEFINED"],
            checks=[],
        )

    total_weight = sum(c.weight for c in checks)
    passed_weight = sum(c.weight for c in checks if c.passed)
    tests_total = len(checks)
    tests_passed = sum(1 for c in checks if c.passed)
    tests_failed = tests_total - tests_passed

    raw_score = (passed_weight / total_weight * 100.0) if total_weight > 0 else 0.0

    blocking_failures = [c.name for c in checks if c.blocking and not c.passed]
    evidence = [
        {
            "check": c.name,
            "passed": c.passed,
            "weight": c.weight,
            "blocking": c.blocking,
            "message": c.message,
            "details": c.details,
        }
        for c in checks
    ]

    if blocking_failures:
        final_score = min(raw_score, 59.0)
        status = "FAIL"
    else:
        final_score = raw_score
        status = "PASS" if final_score >= min_threshold else "FAIL"

    return CategoryResult(
        category=category,
        score=round(final_score, 1),
        status=status,
        tests_total=tests_total,
        tests_passed=tests_passed,
        tests_failed=tests_failed,
        evidence=evidence,
        blocking_failures=blocking_failures,
        checks=checks,
    )
