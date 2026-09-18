"""Tests for authoritative BudgetManager tracking, priority shedding, and audit records."""

from __future__ import annotations


from intelligence.budgets.manager import BudgetManager
from intelligence.coverage import resolve_micro_topic_status, CoverageState


def test_budget_manager_enforces_ai_call_limit_and_protects_p0():
    manager = BudgetManager(global_limits={"max_ai_calls": 2})

    # First call P1 -> ok
    can_exec, reason = manager.can_execute("topic-1", priority="P1")
    assert can_exec is True
    manager.consume("topic-1", "ai_calls", 1)

    # Second call P1 -> ok
    can_exec, reason = manager.can_execute("topic-2", priority="P1")
    assert can_exec is True
    manager.consume("topic-2", "ai_calls", 1)

    # Budget is now exhausted (2/2)
    # P2 cannot execute
    can_exec_p2, reason_p2 = manager.can_execute("topic-3", priority="P2")
    assert can_exec_p2 is False
    assert reason_p2 == "GLOBAL_AI_CALL_BUDGET_EXHAUSTED"

    # P0 cannot execute once remaining is 0
    can_exec_p0, reason_p0 = manager.can_execute("topic-0", priority="P0")
    assert can_exec_p0 is False


def test_budget_manager_records_explicit_skips():
    manager = BudgetManager()
    record = manager.skip(
        micro_topic_id="space:launches",
        reason="GLOBAL_AI_CALL_BUDGET_EXHAUSTED",
        priority="P2",
    )
    assert record.status == "BUDGET_SKIPPED"
    assert record.reason == "GLOBAL_AI_CALL_BUDGET_EXHAUSTED"

    snapshot = manager.snapshot()
    assert snapshot["total_skips"] == 1
    assert snapshot["skips"][0]["micro_topic_id"] == "space:launches"


def test_budget_skip_is_never_converted_to_no_major_update():
    """Verify Section 13 invariant: a budget skip must never become NO_MAJOR_UPDATE."""
    skip_record = {"status": "BUDGET_SKIPPED", "reason": "BUDGET_EXHAUSTED"}
    evaluation = {"evaluation_status": "EVALUATION_COMPLETE", "evaluated": True}
    assignments = [{"micro_topic": "rag", "importance_score": 50, "candidate_count": 3}]

    status, reason = resolve_micro_topic_status(assignments, evaluation, budget_record=skip_record)
    assert status == CoverageState.BUDGET_SKIPPED
    assert status != CoverageState.CHECKED_NO_MAJOR_UPDATE
    assert "BUDGET" in reason
