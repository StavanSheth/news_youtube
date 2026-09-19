"""236 Micro-topic theme coverage validator and CLI report generator."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .quality import (
    generate_theme_health_json,
    theme_quality_score,
    theme_specificity_score,
    validate_theme_completeness,
)


class ThemeCoverageValidator:
    """Validator ensuring 100% coverage and bidirectional integrity for all 236 micro-topics."""

    def __init__(
        self,
        matrix_records: list[dict[str, Any]],
        themes: list[dict[str, Any]],
    ) -> None:
        self.records = matrix_records
        self.themes = themes
        self._record_map = {(r.get("domain"), r.get("id")): r for r in matrix_records}
        self._theme_by_mt = {
            (t.get("domain"), t.get("micro_topic_id") or t.get("micro_topic")): t
            for t in themes
            if t.get("micro_topic_id") or (t.get("micro_topic") not in {"any", "*", None})
        }

    def check_duplicate_ids(self) -> list[str]:
        """Detect any duplicate theme IDs."""
        seen = set()
        duplicates = []
        for theme in self.themes:
            tid = theme.get("id") or theme.get("theme_id")
            if not tid:
                continue
            if tid in seen:
                duplicates.append(tid)
            seen.add(tid)
        return duplicates

    def check_bidirectional(self) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        """Verify bidirectional mapping: every matrix record has a theme, and no orphan themes exist."""
        uncovered = [
            (r.get("domain", ""), r["id"]) for r in self.records
            if (r.get("domain"), r["id"]) not in self._theme_by_mt
        ]
        orphans = [
            key for key in self._theme_by_mt
            if key not in self._record_map
        ]
        return uncovered, orphans

    def validate_all(self, min_specificity: float = 0.0) -> dict[str, Any]:
        """Validate coverage, completeness, and specificity for all 236 micro-topics."""
        duplicates = self.check_duplicate_ids()
        uncovered, orphans = self.check_bidirectional()

        failures: list[dict[str, Any]] = []
        passed: list[dict[str, Any]] = []
        low_specificity: list[dict[str, Any]] = []

        for record in self.records:
            mt_id = record.get("id", "")
            domain = record.get("domain", "")
            theme = self._theme_by_mt.get((domain, mt_id))
            if not theme:
                failures.append({
                    "micro_topic_id": mt_id,
                    "domain": domain,
                    "reason": "Missing bespoke theme",
                })
                continue

            ok, errors, warnings = validate_theme_completeness(theme)
            spec = theme_specificity_score(theme)
            qual = theme_quality_score(theme)

            item = {
                "micro_topic_id": mt_id,
                "theme_id": theme.get("id") or theme.get("theme_id"),
                "domain": record.get("domain", ""),
                "specificity_score": spec,
                "quality_score": qual,
                "errors": errors,
                "warnings": warnings,
            }

            if not ok:
                failures.append(item)
            else:
                passed.append(item)

            if spec < min_specificity:
                low_specificity.append(item)

        total = len(self.records)
        covered_count = len(passed)
        coverage_pct = round((covered_count / max(1, total)) * 100, 2)

        return {
            "total_records": total,
            "covered_count": covered_count,
            "uncovered_count": len(uncovered),
            "orphan_count": len(orphans),
            "duplicate_ids": duplicates,
            "coverage_percentage": coverage_pct,
            "uncovered_micro_topics": uncovered,
            "orphan_micro_topics": orphans,
            "failures": failures,
            "low_specificity": low_specificity,
            "is_complete": len(uncovered) == 0 and len(failures) == 0 and len(duplicates) == 0,
        }

    def generate_coverage_report(self) -> dict[str, Any]:
        """Generate structured coverage report per Set E Section 5."""
        val = self.validate_all()
        by_domain: dict[str, dict[str, int]] = {}
        for r in self.records:
            domain = r.get("domain", "unknown")
            by_domain.setdefault(domain, {"total": 0, "covered": 0})
            by_domain[domain]["total"] += 1
            if (domain, r.get("id")) in self._theme_by_mt:
                by_domain[domain]["covered"] += 1

        return {
            "summary": {
                "total_micro_topics": len(self.records),
                "bespoke_themes": len(self._theme_by_mt),
                "coverage_pct": val["coverage_percentage"],
                "complete": val["is_complete"],
            },
            "domain_breakdown": by_domain,
            "validation_details": val,
        }

    def generate_health_json(self) -> dict[str, Any]:
        return generate_theme_health_json(self.records, self.themes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Micro-topic theme coverage and health validator")
    parser.add_argument("--all", action="store_true", help="Validate all 236 micro-topics")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--specificity", action="store_true", help="Check specificity scores")
    parser.add_argument("--min-score", type=float, default=0.3, help="Minimum specificity score threshold")
    parser.add_argument("--source", type=str, default="", help="Inspect theme resolution for a single micro-topic ID")
    parser.add_argument("--fail-on-error", action="store_true", help="Exit with non-zero status if validation fails")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parent.parent.parent.parent
    matrix_path = root / "config" / "microtopic_matrix.json"
    if not matrix_path.exists():
        print(f"Error: {matrix_path} not found", file=sys.stderr)
        return 1

    with matrix_path.open(encoding="utf-8-sig") as f:
        matrix_data = json.load(f)
    records = matrix_data.get("records", [])

    from intelligence.config import load_config
    app_config = load_config(root)
    themes = app_config.themes

    validator = ThemeCoverageValidator(records, themes)

    if args.source:
        theme = next(
            (t for t in themes if (t.get("micro_topic_id") or t.get("micro_topic")) == args.source),
            None,
        )
        if not theme:
            print(f"No bespoke theme found for micro-topic: {args.source}")
            return 1
        spec = theme_specificity_score(theme)
        qual = theme_quality_score(theme)
        ok, errors, warnings = validate_theme_completeness(theme)
        print(f"Micro-topic: {args.source}")
        print(f"Theme ID: {theme.get('id')}")
        print(f"Specificity Score: {spec:.3f}")
        print(f"Quality Score: {qual:.3f}")
        print(f"Status: {'PASS' if ok else 'FAIL'}")
        if errors:
            print(f"Errors: {errors}")
        if warnings:
            print(f"Warnings: {warnings}")
        return 0 if ok else 1

    min_score = args.min_score if args.specificity else 0.0
    results = validator.validate_all(min_specificity=min_score)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("=" * 60)
        print("THEME ENGINE COVERAGE & QUALITY REPORT")
        print("=" * 60)
        print(f"Total Micro-Topics: {results['total_records']}")
        print(f"Covered with Bespoke Themes: {results['covered_count']}")
        print(f"Coverage: {results['coverage_percentage']}%")
        print(f"Duplicate IDs: {len(results['duplicate_ids'])}")
        print(f"Orphan Themes: {results['orphan_count']}")
        print(f"Validation Failures: {len(results['failures'])}")
        if args.specificity:
            print(f"Themes Below Min Specificity ({min_score}): {len(results['low_specificity'])}")
        print("=" * 60)
        if results["is_complete"]:
            print("STATUS: ALL 236 MICRO-TOPIC THEMES VALIDATED (PASS)")
        else:
            print("STATUS: INCOMPLETE COVERAGE OR VALIDATION FAILURES (FAIL)")

    if args.fail_on_error and not results["is_complete"]:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
