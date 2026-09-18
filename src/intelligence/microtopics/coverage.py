"""Truthful coverage states and evaluation ledger for micro-topics."""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from ..coverage import CoverageState, resolve_micro_topic_status


CANONICAL_COVERAGE_STATES = {
    "MAJOR_UPDATE",
    "MINOR_UPDATE",
    "NO_MAJOR_UPDATE",
    "NO_RELEVANT_CONTENT",
    "INSUFFICIENT_EVIDENCE",
    "BUDGET_SKIPPED",
    "TRANSCRIPT_UNAVAILABLE",
    "ERROR",
    "SOURCE_FAILURE",
}


def evaluate_micro_topic_status(
    assignments: list[dict[str, Any]],
    evaluation: dict[str, Any],
    budget_record: dict[str, Any] | None = None,
) -> str:
    """Return a truthful final state by delegating to authoritative coverage state machine."""
    # Check for explicit source failure first
    for item in assignments:
        if item.get("source_status") == "SOURCE_FAILURE":
            return CoverageState.SOURCE_FAILURE

    # Explicit check for technical errors in assignments or evaluation
    if evaluation.get("evaluation_status") == "FAILED" or evaluation.get("error"):
        return "ERROR"
    for item in assignments:
        if item.get("retrieval_status") == "RETRIEVAL_FAILURE" or item.get("analysis_status") == "ANALYSIS_FAILURE":
            return "ERROR"
        if item.get("error") or item.get("status") == "ERROR":
            return "ERROR"

    status, _ = resolve_micro_topic_status(assignments, evaluation, budget_record=budget_record)
    if status == CoverageState.SOURCE_FAILURE:
        return CoverageState.SOURCE_FAILURE
    if status not in CANONICAL_COVERAGE_STATES:
        if "NO_MAJOR_UPDATE" in status:
            return "NO_MAJOR_UPDATE"
        if "NO_RELEVANT_CONTENT" in status:
            return "NO_RELEVANT_CONTENT"
        if "INSUFFICIENT_EVIDENCE" in status:
            return "INSUFFICIENT_EVIDENCE"
        return "ERROR"
    return status


def coverage(
    entries: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
    source_health: dict[str, Any],
) -> list[dict[str, Any]]:
    """Report evaluated coverage without treating unchecked leaves as no update."""
    assigned: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for assignment in assignments:
        assigned[(assignment["domain"], assignment["micro_topic"])].append(assignment)
    ledger = source_health.get("evaluation_ledger", {})
    rows = []
    for entry in entries:
        evidence = assigned[(entry["domain"], entry["micro_topic"])]
        evaluation_key = f"{entry['domain']}:{entry['micro_topic']}"
        evaluation = ledger.get(evaluation_key, {})
        if evidence and not evaluation and any(
            item.get("evidence_available", bool(item.get("relevant_count", 0) or item.get("evidence_count", 0)))
            for item in evidence
        ):
            evaluation = {"evaluation_status": "EVALUATION_COMPLETE"}
        checked = evaluation.get("evaluation_status") == "EVALUATION_COMPLETE"
        if not checked:
            checked = evaluation_key in source_health.get("evaluated_micro_topics", [])
            evaluation = {
                **evaluation,
                "evaluation_status": "EVALUATION_COMPLETE" if checked else "NOT_STARTED",
            }
        searched = checked
        status = evaluate_micro_topic_status(evidence, evaluation)
        candidate_count = sum(int(item.get("candidate_count", 0)) for item in evidence)
        relevant_count = sum(int(item.get("relevant_count", 0)) for item in evidence)
        event_count = sum(int(item.get("event_count", 0)) for item in evidence)
        publishable_count = sum(int(item.get("publishable_count", 0)) for item in evidence)
        rows.append({
            "domain": entry["domain"],
            "topic": entry["topic"],
            "micro_topic": entry["micro_topic"],
            "status": status,
            "searched": searched,
            "candidate_count": candidate_count,
            "relevant_count": relevant_count,
            "event_count": event_count,
            "publishable_count": publishable_count,
            "evidence_count": len(evidence),
        })
    return rows
