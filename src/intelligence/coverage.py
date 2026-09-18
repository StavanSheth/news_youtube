"""Truthful micro-topic evaluation ledger and no-update state machine."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .statuses import IntelligenceStatus


class CoverageState:
    NOT_STARTED = "NOT_STARTED"
    CHECKED_NO_RELEVANT_CONTENT = "NO_RELEVANT_CONTENT"
    CHECKED_NO_MAJOR_UPDATE = "NO_MAJOR_UPDATE"
    CHECKED_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    MAJOR_UPDATE = "MAJOR_UPDATE"
    MINOR_UPDATE = "MINOR_UPDATE"
    BUDGET_SKIPPED = "BUDGET_SKIPPED"
    TRANSCRIPT_UNAVAILABLE = "TRANSCRIPT_UNAVAILABLE"
    ERROR = "ERROR"


@dataclass
class MicroTopicLedgerRow:
    micro_topic_id: str
    domain: str
    topic: str
    enabled: bool = True
    sources_checked: int = 0
    candidate_count: int = 0
    relevant_count: int = 0
    evidence_count: int = 0
    retrieval_status: str = "OK"
    analysis_status: str = "OK"
    validation_status: str = "VALID"
    budget_status: str = "OK"
    final_status: str = "NOT_STARTED"
    status_reason: str = ""
    last_checked_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    run_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "micro_topic_id": self.micro_topic_id,
            "domain": self.domain,
            "topic": self.topic,
            "enabled": self.enabled,
            "sources_checked": self.sources_checked,
            "candidate_count": self.candidate_count,
            "relevant_count": self.relevant_count,
            "evidence_count": self.evidence_count,
            "retrieval_status": self.retrieval_status,
            "analysis_status": self.analysis_status,
            "validation_status": self.validation_status,
            "budget_status": self.budget_status,
            "final_status": self.final_status,
            "status_reason": self.status_reason,
            "last_checked_at": self.last_checked_at,
            "run_id": self.run_id,
            # Backwards-compatible aliases for existing tests
            "status": self.final_status,
            "searched": self.final_status != CoverageState.NOT_STARTED,
            "publishable_count": self.relevant_count,
            "event_count": min(self.relevant_count, 1),
        }


def resolve_micro_topic_status(
    assignments: list[dict[str, Any]],
    evaluation: dict[str, Any],
    budget_record: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Resolve truthful no-update status; never conflate budget skips or errors with NO_MAJOR_UPDATE."""
    # Check for budget skips first
    if budget_record and budget_record.get("status") == "BUDGET_SKIPPED":
        return CoverageState.BUDGET_SKIPPED, str(budget_record.get("reason", "BUDGET_SKIPPED"))
    if any(item.get("budget_skipped") for item in assignments):
        return CoverageState.BUDGET_SKIPPED, "BUDGET_LIMIT_EXCEEDED"

    # Check for technical errors
    for item in assignments:
        if item.get("source_status") == IntelligenceStatus.SOURCE_FAILURE.value:
            return CoverageState.ERROR, "SOURCE_FAILURE"
        if item.get("retrieval_status") == IntelligenceStatus.RETRIEVAL_FAILURE.value:
            return CoverageState.ERROR, "RETRIEVAL_FAILURE"
        if item.get("analysis_status") == IntelligenceStatus.ANALYSIS_FAILURE.value:
            return CoverageState.ERROR, "ANALYSIS_FAILURE"

    # Check evaluation state
    eval_status = evaluation.get("evaluation_status", "")
    if eval_status == "NOT_STARTED":
        return CoverageState.CHECKED_INSUFFICIENT_EVIDENCE, "EVALUATION_NOT_STARTED"

    if assignments and any(
        item.get("evidence_available") is False
        or item.get("status") == "INSUFFICIENT_EVIDENCE"
        for item in assignments
    ):
        return CoverageState.CHECKED_INSUFFICIENT_EVIDENCE, "EVIDENCE_NOT_AVAILABLE"

    if eval_status != "EVALUATION_COMPLETE" and not evaluation.get("evaluated"):
        return CoverageState.CHECKED_INSUFFICIENT_EVIDENCE, "INSUFFICIENT_EVALUATION"

    # If evaluated but zero relevant content exists
    if not assignments or not any(
        item.get("relevant_count", 0) > 0 or item.get("evidence_count", 0) > 0 or item.get("candidate_count", 0) > 0
        for item in assignments
    ):
        return CoverageState.CHECKED_NO_RELEVANT_CONTENT, "NO_QUALIFYING_CONTENT_FOUND"

    # Content exists and was evaluated
    maximum_importance = max(float(item.get("importance_score", 0)) for item in assignments)
    if maximum_importance >= 75:
        return CoverageState.MAJOR_UPDATE, f"IMPORTANCE_SCORE_{maximum_importance:.0f}"

    if any(item.get("material_change", False) for item in assignments):
        return CoverageState.MINOR_UPDATE, "MATERIAL_CHANGE_DETECTED"

    return CoverageState.CHECKED_NO_MAJOR_UPDATE, "EVALUATED_BELOW_PUBLICATION_THRESHOLD"


def build_coverage_ledger(
    entries: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
    source_health: dict[str, Any],
    budget_skips: list[dict[str, Any]] | None = None,
    run_id: str = "",
) -> list[dict[str, Any]]:
    """Build truthful 16-field coverage ledger for every enabled micro-topic."""
    assigned: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for assignment in assignments:
        assigned[(assignment.get("domain", ""), assignment.get("micro_topic", ""))].append(assignment)

    budget_by_topic: dict[str, dict[str, Any]] = {}
    for skip in (budget_skips or []):
        budget_by_topic[skip.get("micro_topic_id", "")] = skip

    ledger = source_health.get("evaluation_ledger", {})
    evaluated_list = source_health.get("evaluated_micro_topics", [])
    now_iso = datetime.now(UTC).isoformat()
    rows = []

    for entry in entries:
        domain = entry.get("domain", "")
        micro_topic = entry.get("micro_topic", "")
        topic = entry.get("topic", "")
        micro_topic_id = entry.get("micro_topic_id", f"{domain}:{micro_topic}")
        evidence = assigned[(domain, micro_topic)]

        evaluation_key = f"{domain}:{micro_topic}"
        evaluation = dict(ledger.get(evaluation_key, {}))

        # Check if evaluated via legacy boolean or list
        if source_health.get("evaluated") and not evaluation:
            evaluation["evaluation_status"] = "EVALUATION_COMPLETE"
            evaluation["evaluated"] = True
        elif evidence and not evaluation and any(
            item.get("evidence_available", bool(item.get("relevant_count", 0) or item.get("evidence_count", 0)))
            for item in evidence
        ):
            evaluation["evaluation_status"] = "EVALUATION_COMPLETE"
            evaluation["evaluated"] = True
        elif evaluation_key in evaluated_list:
            evaluation["evaluation_status"] = "EVALUATION_COMPLETE"
            evaluation["evaluated"] = True

        skip_record = budget_by_topic.get(micro_topic_id) or budget_by_topic.get(micro_topic)
        final_status, reason = resolve_micro_topic_status(evidence, evaluation, skip_record)

        candidate_count = sum(int(item.get("candidate_count", 0)) for item in evidence)
        relevant_count = sum(int(item.get("relevant_count", 0)) for item in evidence)
        sources_checked = int(source_health.get("healthy_sources", 1))

        row = MicroTopicLedgerRow(
            micro_topic_id=micro_topic_id,
            domain=domain,
            topic=topic,
            enabled=bool(entry.get("enabled", True)),
            sources_checked=sources_checked,
            candidate_count=candidate_count,
            relevant_count=relevant_count,
            evidence_count=len(evidence),
            retrieval_status="ERROR" if final_status == CoverageState.ERROR else "OK",
            analysis_status="ERROR" if final_status == CoverageState.ERROR else "OK",
            validation_status="VALID",
            budget_status="BUDGET_SKIPPED" if final_status == CoverageState.BUDGET_SKIPPED else "OK",
            final_status=final_status,
            status_reason=reason,
            last_checked_at=now_iso,
            run_id=run_id,
        )
        # Preserve backwards-compatible dictionary format
        row_dict = row.to_dict()
        row_dict["micro_topic"] = micro_topic
        row_dict["publishable_count"] = sum(int(item.get("publishable_count", 0)) for item in evidence)
        row_dict["event_count"] = sum(int(item.get("event_count", 0)) for item in evidence)
        rows.append(row_dict)

    return rows
