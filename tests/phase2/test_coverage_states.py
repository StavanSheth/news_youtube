"""Phase 2A tests for truthful coverage states and error handling."""

from __future__ import annotations

from intelligence.microtopics.coverage import (
    CANONICAL_COVERAGE_STATES,
    evaluate_micro_topic_status,
)


def test_technical_failure_must_be_error():
    # Technical error in evaluation must be ERROR, not NO_MAJOR_UPDATE or NO_RELEVANT_CONTENT
    failed_eval = {"evaluation_status": "FAILED", "error": "ProviderTimeoutError"}
    status = evaluate_micro_topic_status([], failed_eval)
    assert status == "ERROR"

    # Technical error in retrieval must be ERROR
    assignments = [{"retrieval_status": "RETRIEVAL_FAILURE"}]
    status2 = evaluate_micro_topic_status(assignments, {"evaluation_status": "EVALUATION_COMPLETE"})
    assert status2 == "ERROR"

    # Technical error in analysis must be ERROR
    assignments3 = [{"analysis_status": "ANALYSIS_FAILURE"}]
    status3 = evaluate_micro_topic_status(assignments3, {"evaluation_status": "EVALUATION_COMPLETE"})
    assert status3 == "ERROR"


def test_no_update_requires_genuine_evaluation():
    # Evaluated with candidate items but importance below threshold -> NO_MAJOR_UPDATE
    assignments = [
        {"candidate_count": 2, "relevant_count": 1, "importance_score": 30, "material_change": False}
    ]
    evaluation = {"evaluation_status": "EVALUATION_COMPLETE"}
    status = evaluate_micro_topic_status(assignments, evaluation)
    assert status == "NO_MAJOR_UPDATE"

    # Evaluated but zero qualifying content -> NO_RELEVANT_CONTENT
    assignments_zero = [{"candidate_count": 0, "relevant_count": 0}]
    status_zero = evaluate_micro_topic_status(assignments_zero, evaluation)
    assert status_zero == "NO_RELEVANT_CONTENT"


def test_budget_skipped_status():
    budget_rec = {"status": "BUDGET_SKIPPED", "reason": "P0_PROTECTED"}
    status = evaluate_micro_topic_status([], {}, budget_record=budget_rec)
    assert status == "BUDGET_SKIPPED"


def test_all_states_belong_to_canonical_set():
    eval_complete = {"evaluation_status": "EVALUATION_COMPLETE"}
    s1 = evaluate_micro_topic_status([{"importance_score": 85, "relevant_count": 1}], eval_complete)
    assert s1 == "MAJOR_UPDATE"
    assert s1 in CANONICAL_COVERAGE_STATES

    s2 = evaluate_micro_topic_status([{"material_change": True, "importance_score": 40, "relevant_count": 1}], eval_complete)
    assert s2 == "MINOR_UPDATE"
    assert s2 in CANONICAL_COVERAGE_STATES
