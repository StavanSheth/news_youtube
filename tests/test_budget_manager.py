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


def test_global_budget():
    """Verify global budget ceiling enforcement across microtopics."""
    manager = BudgetManager(global_limits={"max_ai_calls": 3})
    ok, reason, _ = manager.authorize("topic-A", priority="P1", estimated_calls=2)
    assert ok
    manager.consume("topic-A", "ai_calls", 2)

    # 1 call left
    ok, reason, _ = manager.authorize("topic-B", priority="P1", estimated_calls=2)
    assert not ok
    assert "BUDGET_EXHAUSTED" in reason


def test_microtopic_budget():
    """Verify micro-topic level limits independently bound usage."""
    manager = BudgetManager(
        global_limits={"max_ai_calls": 10},
        micro_topic_limits={"topic-C": {"max_ai_calls": 1}},
    )
    ok, _, _ = manager.authorize("topic-C", priority="P1", estimated_calls=1)
    assert ok
    manager.consume("topic-C", "ai_calls", 1)

    ok2, reason2, skip = manager.authorize("topic-C", priority="P1", estimated_calls=1)
    assert not ok2
    assert reason2 == "MICRO_TOPIC_AI_CALL_LIMIT_EXCEEDED"
    assert skip is not None
    assert skip.status == "BUDGET_SKIPPED"


def test_p0_reserve():
    """Verify P0 reserved capacity blocks lower priority execution when low on calls."""
    manager = BudgetManager(
        global_limits={"max_ai_calls": 4, "p0_reserve": 2}
    )
    # Consumes 2 calls
    manager.consume("topic-X", "ai_calls", 2)

    # Now 2 calls left, which matches p0_reserve=2.
    # P1 request should be rejected to protect P0.
    ok_p1, reason_p1, _ = manager.authorize("topic-P1", priority="P1", estimated_calls=1)
    assert not ok_p1
    assert reason_p1 == "RESERVED_FOR_P0"

    # P0 request should be permitted
    ok_p0, reason_p0, _ = manager.authorize("topic-P0", priority="P0", estimated_calls=1)
    assert ok_p0
    assert reason_p0 == "AUTHORIZED"


def test_budget_skip():
    """Verify explicit skip record generation with complete audit details."""
    manager = BudgetManager(global_limits={"max_ai_calls": 1})
    manager.consume("topic-1", "ai_calls", 1)

    ok, reason, record = manager.authorize("topic-2", priority="P2", estimated_calls=1, run_id="run-123")
    assert not ok
    assert record is not None
    assert record.status == "BUDGET_SKIPPED"
    assert record.micro_topic_id == "topic-2"
    assert record.details["run_id"] == "run-123"


def test_budget_reconciliation():
    """Verify reservation and consumption properly reconcile active reserved units."""
    manager = BudgetManager(global_limits={"max_ai_calls": 5})
    ok, _, _ = manager.authorize("topic-R", priority="P1", estimated_calls=2)
    assert ok
    assert manager._dimension_reservations["ai_calls"] == 2

    # Consuming 2 reconciles the reservation
    manager.consume("topic-R", "ai_calls", 2)
    assert manager._dimension_reservations["ai_calls"] == 0
    assert manager.global_usage.ai_calls == 2


def test_no_overrun():
    """Verify execution authorization prevents overrunning limits."""
    manager = BudgetManager(global_limits={"max_ai_calls": 2})
    ok1, _, _ = manager.authorize("topic-1", priority="P1", estimated_calls=2)
    assert ok1
    manager.consume("topic-1", "ai_calls", 2)

    ok2, _, _ = manager.authorize("topic-2", priority="P1", estimated_calls=1)
    assert not ok2
    assert manager.global_usage.ai_calls == 2

