"""Truthful coverage states and evaluation ledger for micro-topics."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
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


def build_source_microtopic_matrix(
    records: list[dict[str, Any]],
    sources: list[Any],
    source_health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate deterministic source coverage matrix for microtopics per Section 11.

    Required states:
    - COVERED
    - PARTIAL
    - SOURCE_FAILURE
    - NO_SOURCE
    - INSUFFICIENT_EVIDENCE
    """
    health = source_health or {}
    results = []
    status_counts: dict[str, int] = {
        "COVERED": 0,
        "PARTIAL": 0,
        "SOURCE_FAILURE": 0,
        "NO_SOURCE": 0,
        "INSUFFICIENT_EVIDENCE": 0,
    }

    for record in records:
        mt_id = record.get("id") or record.get("micro_topic")
        domain = record.get("domain")
        topic = record.get("topic")

        configured = []
        for s in sources:
            s_dict = s.to_dict() if hasattr(s, "to_dict") else dict(s)
            s_domains = s_dict.get("domains", [])
            s_topics = s_dict.get("topics", [])
            s_mts = s_dict.get("micro_topics", [])

            if mt_id and mt_id in s_mts:
                configured.append(s_dict)
            elif topic and topic in s_topics and domain and domain in s_domains:
                configured.append(s_dict)
            elif domain and domain in s_domains and not s_mts and not s_topics:
                configured.append(s_dict)

        source_count = len(configured)
        enabled_sources = [s for s in configured if s.get("enabled")]
        ready_sources = []
        fresh_sources = []
        failed_sources = []
        rag_eligible_sources = []

        for s_dict in configured:
            sid = s_dict.get("id") or s_dict.get("source_id")
            s_h = health.get(sid, {})
            status = s_h.get("status") or ("READY" if s_dict.get("enabled") else "CONFIGURED")
            if status in ("READY", "PASS", "HEALTHY"):
                ready_sources.append(s_dict)
                if s_h.get("fresh", True):
                    fresh_sources.append(s_dict)
                if status != "QUARANTINED":
                    rag_eligible_sources.append(s_dict)
            elif status in ("FAILED", "SOURCE_FAILURE", "ERROR"):
                failed_sources.append(s_dict)

        ready_source_count = len(ready_sources)
        enabled_source_count = len(enabled_sources)
        healthy_source_count = ready_source_count
        fresh_source_count = len(fresh_sources)
        usable_source_count = len([s for s in ready_sources if s.get("enabled")])
        rag_eligible_source_count = len(rag_eligible_sources)
        evidence_capable = usable_source_count > 0 or fresh_source_count > 0

        if source_count == 0:
            coverage_status = "NO_SOURCE"
        elif failed_sources and ready_source_count == 0:
            coverage_status = "SOURCE_FAILURE"
        elif fresh_source_count >= 2:
            coverage_status = "COVERED"
        elif fresh_source_count == 1:
            coverage_status = "PARTIAL"
        elif ready_source_count > 0 and fresh_source_count == 0:
            coverage_status = "INSUFFICIENT_EVIDENCE"
        else:
            coverage_status = "PARTIAL" if source_count > 0 else "NO_SOURCE"

        status_counts[coverage_status] = status_counts.get(coverage_status, 0) + 1

        results.append({
            "micro_topic_id": mt_id,
            "domain": domain,
            "topic": topic,
            "source_count": source_count,
            "enabled_source_count": enabled_source_count,
            "healthy_source_count": healthy_source_count,
            "fresh_source_count": fresh_source_count,
            "usable_source_count": usable_source_count,
            "rag_eligible_source_count": rag_eligible_source_count,
            "ready_source_count": ready_source_count,
            "evidence_capable": evidence_capable,
            "status": coverage_status,
            "coverage_status": coverage_status,
            "usable_protection": "NO_USABLE_SOURCE" if usable_source_count == 0 else "USABLE",
        })

    return {
        "total_microtopics": len(records),
        "status_counts": status_counts,
        "matrix": results,
    }


def check_microtopic_source_protection(coverage_record: dict[str, Any]) -> tuple[bool, str]:
    """If a micro-topic has 0 usable sources, protection triggers returning NO_USABLE_SOURCE."""
    usable = coverage_record.get("usable_source_count", 0) or coverage_record.get("ready_source_count", 0)
    if usable == 0:
        return False, "NO_USABLE_SOURCE"
    return True, "USABLE"


def generate_source_microtopic_coverage_report(
    matrix_records: list[dict[str, Any]],
    sources: list[Any],
    output_file: Path,
    source_health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate source_microtopic_coverage.json per Section 33."""
    import json
    matrix_data = build_source_microtopic_matrix(matrix_records, sources, source_health=source_health)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(matrix_data, indent=2), encoding="utf-8")
    return matrix_data
