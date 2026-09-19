"""Theme review lifecycle management, verification, and report generator."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from .contracts import validate_theme_contract
from .quality import (
    is_generic_theme,
    theme_specificity_score,
)
from .snapshots import compute_theme_fingerprint


class ThemeReviewStatus(StrEnum):
    DRAFT = "DRAFT"
    AI_VALIDATED = "AI_VALIDATED"
    SEMANTIC_VALIDATED = "SEMANTIC_VALIDATED"
    HUMAN_REVIEWED = "HUMAN_REVIEWED"
    APPROVED = "APPROVED"


def evaluate_theme_review_record(theme: dict[str, Any]) -> dict[str, Any]:
    """Evaluate review status and semantic quality of a theme record."""
    theme_id = theme.get("theme_id") or theme.get("id", "unknown")
    micro_topic_id = theme.get("micro_topic_id") or theme.get("micro_topic", "unknown")
    domain = theme.get("domain", "unknown")

    contract_diag = validate_theme_contract(theme)
    specificity = round(theme_specificity_score(theme), 3)
    questions = theme.get("questions", [])
    evidence = theme.get("evidence_requirements", []) or theme.get("evidence", {}).get("required", [])

    fingerprint = compute_theme_fingerprint(theme)
    is_generic = is_generic_theme(theme)

    current_status = str(theme.get("review_status", ThemeReviewStatus.AI_VALIDATED.value)).upper()

    blocking_issues: list[str] = []
    if not contract_diag.get("valid"):
        blocking_issues.append("CONTRACT_INVALID")
    if is_generic:
        blocking_issues.append("GENERIC_THEME_DETECTED")
    if specificity < 0.50:
        blocking_issues.append(f"LOW_SPECIFICITY_{specificity}")
    if len(questions) < 4:
        blocking_issues.append("INSUFFICIENT_QUESTIONS")
    if not evidence:
        blocking_issues.append("MISSING_EVIDENCE_RULES")

    # Determine advanced validation state
    computed_status = current_status
    if not blocking_issues:
        if current_status in (ThemeReviewStatus.AI_VALIDATED.value, ThemeReviewStatus.DRAFT.value):
            computed_status = ThemeReviewStatus.SEMANTIC_VALIDATED.value

    return {
        "theme_id": theme_id,
        "micro_topic_id": micro_topic_id,
        "domain": domain,
        "specificity": specificity,
        "question_count": len(questions),
        "evidence_count": len(evidence),
        "duplicate_fingerprint": fingerprint[:12],
        "neighboring_topic_risk": "LOW" if specificity >= 0.60 else "MEDIUM",
        "review_status": computed_status,
        "approval_status": "APPROVED" if computed_status in (ThemeReviewStatus.HUMAN_REVIEWED.value, ThemeReviewStatus.APPROVED.value) else "PENDING_HUMAN_REVIEW",
        "contract_valid": contract_diag.get("valid", False),
        "blocking_issues": blocking_issues,
    }


def generate_theme_review_reports(
    themes: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, Any]:
    """Generate theme_review_report.json and theme_review_report.md."""
    output_dir.mkdir(parents=True, exist_ok=True)
    records = [evaluate_theme_review_record(t) for t in themes]

    total = len(records)
    semantic_validated = sum(1 for r in records if r["review_status"] in (
        ThemeReviewStatus.SEMANTIC_VALIDATED.value,
        ThemeReviewStatus.HUMAN_REVIEWED.value,
        ThemeReviewStatus.APPROVED.value,
    ))
    approved = sum(1 for r in records if r["approval_status"] == "APPROVED")
    blocked = sum(1 for r in records if r["blocking_issues"])

    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_themes": total,
        "semantic_validated_count": semantic_validated,
        "human_approved_count": approved,
        "human_review_completion_pct": round((approved / max(1, total)) * 100.0, 1),
        "machine_validation_completion_pct": round((semantic_validated / max(1, total)) * 100.0, 1),
        "blocked_count": blocked,
        "average_specificity": round(sum(r["specificity"] for r in records) / max(1, total), 3),
        "themes": records,
    }

    # Write JSON
    json_path = output_dir / "theme_review_report.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Write Markdown
    md_lines = [
        "# 236 Micro-Topic Theme Review & Quality Certification Report",
        "",
        f"- **Generated At**: {summary['generated_at']}",
        f"- **Total Themes Audited**: {total}",
        f"- **Machine & Semantic Validated**: {semantic_validated} ({summary['machine_validation_completion_pct']}%)",
        f"- **Certified Approved**: {approved} ({summary['human_review_completion_pct']}%)",
        f"- **Average Specificity Score**: {summary['average_specificity']}",
        f"- **Blocking Issues**: {blocked}",
        "",
        "## Domain Breakdown & Sample Themes",
        "",
        "| Theme ID | Micro-Topic | Domain | Specificity | Questions | Evidence | Status | Blocking Issues |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for r in records[:30]:  # Top sample in table
        issues = ", ".join(r["blocking_issues"]) if r["blocking_issues"] else "NONE"
        md_lines.append(
            f"| `{r['theme_id']}` | `{r['micro_topic_id']}` | {r['domain']} | {r['specificity']} | {r['question_count']} | {r['evidence_count']} | {r['review_status']} | {issues} |"
        )

    if total > 30:
        md_lines.append(f"\n*(Remaining {total - 30} theme records detailed in theme_review_report.json)*")

    md_path = output_dir / "theme_review_report.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    return summary
