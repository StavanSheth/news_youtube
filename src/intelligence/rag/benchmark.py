"""Authoritative RAG retrieval and provenance benchmark evaluator."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .eligibility import check_chunk_eligibility
from .query import RetrievalRequest
from .ranking import rank_evidence_chunks


def run_rag_retrieval_benchmark(
    fixture_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Execute deterministic RAG evaluation on the golden retrieval benchmark corpus."""
    if fixture_path is None:
        fixture_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "tests"
            / "rag"
            / "fixtures"
            / "golden"
            / "retrieval_benchmark.json"
        )

    if not fixture_path.is_file():
        raise FileNotFoundError(f"RAG benchmark fixture not found at {fixture_path}")

    fixture_data = json.loads(fixture_path.read_text(encoding="utf-8"))
    cases = fixture_data.get("cases", [])

    case_results = []
    precisions = []
    recalls = []
    mrrs = []
    isolation_passed = 0
    provenance_passed = 0
    freshness_passed = 0
    quarantine_passed = 0

    now_utc = datetime(2026, 9, 18, 14, 0, 0, tzinfo=UTC)

    for case in cases:
        case_id = case["id"]
        micro_topic_id = case["micro_topic_id"]
        expected_content_ids = set(case.get("expected_content_ids", []))
        forbidden_sources = set(case.get("forbidden_source_ids", []))
        forbidden_topics = set(case.get("forbidden_micro_topics", []))
        chunks = case.get("test_chunks", [])

        req = RetrievalRequest(
            query=case["query"],
            micro_topic_id=micro_topic_id,
            theme_id=f"theme-{micro_topic_id}",
            max_results=5,
        )

        # 1. Eligibility filter
        eligible_chunks = []
        future_rejected = 0
        quarantine_rejected = 0
        topic_rejected = 0

        for chk in chunks:
            ok, reason = check_chunk_eligibility(chk, req, now=now_utc)
            if ok:
                eligible_chunks.append(chk)
            else:
                if reason == "FUTURE_EVIDENCE_EXCEEDS_CUTOFF":
                    future_rejected += 1
                elif reason == "QUARANTINED_SOURCE":
                    quarantine_rejected += 1
                elif reason == "UNAUTHORIZED_MICRO_TOPIC":
                    topic_rejected += 1

        # 2. Rank evidence
        ranked = rank_evidence_chunks(eligible_chunks, req)

        # 3. Compute retrieval metrics
        retrieved_content_ids = [
            r.get("metadata", {}).get("content_id") for r in ranked if r.get("metadata", {}).get("content_id")
        ]
        retrieved_set = set(retrieved_content_ids)

        tp = len(retrieved_set.intersection(expected_content_ids))
        precision = (tp / max(1, len(retrieved_set))) if retrieved_set else 0.0
        recall = (tp / max(1, len(expected_content_ids))) if expected_content_ids else 0.0

        # Reciprocal rank
        mrr = 0.0
        for rank_idx, cid in enumerate(retrieved_content_ids, start=1):
            if cid in expected_content_ids:
                mrr = 1.0 / rank_idx
                break

        precisions.append(precision)
        recalls.append(recall)
        mrrs.append(mrr)

        # Check provenance completeness
        prov_ok = all(
            bool(
                r.get("metadata", {}).get("source_id")
                and r.get("metadata", {}).get("content_id")
                and r.get("metadata", {}).get("url")
                and r.get("metadata", {}).get("published_at")
            )
            for r in ranked
        )
        if prov_ok:
            provenance_passed += 1

        # Check topic isolation (no forbidden micro-topics retrieved)
        topics_retrieved = {r.get("metadata", {}).get("micro_topic_id") for r in ranked}
        topic_isolated = not bool(topics_retrieved.intersection(forbidden_topics))
        if topic_isolated:
            isolation_passed += 1

        # Check quarantine exclusion
        sources_retrieved = {r.get("metadata", {}).get("source_id") for r in ranked}
        no_quarantined = not bool(sources_retrieved.intersection(forbidden_sources))
        if no_quarantined:
            quarantine_passed += 1

        # Check freshness
        freshness_ok = not any(
            r.get("metadata", {}).get("published_at", "") > "2026-09-18T14:00:00Z"
            for r in ranked
        )
        if freshness_ok:
            freshness_passed += 1

        case_results.append({
            "case_id": case_id,
            "micro_topic_id": micro_topic_id,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "mrr": round(mrr, 3),
            "retrieved_count": len(ranked),
            "provenance_ok": prov_ok,
            "topic_isolated": topic_isolated,
            "no_quarantined": no_quarantined,
            "freshness_ok": freshness_ok,
        })

    n = max(1, len(cases))
    avg_precision = round(sum(precisions) / n, 3)
    avg_recall = round(sum(recalls) / n, 3)
    avg_mrr = round(sum(mrrs) / n, 3)

    summary = {
        "timestamp": datetime.now(UTC).isoformat(),
        "cases_total": n,
        "average_precision": avg_precision,
        "average_recall": avg_recall,
        "average_mrr": avg_mrr,
        "provenance_completeness_pct": round((provenance_passed / n) * 100.0, 1),
        "microtopic_isolation_pct": round((isolation_passed / n) * 100.0, 1),
        "quarantine_exclusion_pct": round((quarantine_passed / n) * 100.0, 1),
        "freshness_compliance_pct": round((freshness_passed / n) * 100.0, 1),
        "status": "PASS" if avg_precision >= 0.85 and avg_recall >= 0.85 and avg_mrr >= 0.85 else "FAIL",
        "cases": case_results,
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return summary
