"""Phase 2C tests for BudgetManager reservation model, P0 priority pool, and audit traces."""

from __future__ import annotations

from intelligence.budgets.manager import BudgetManager


def test_budget_reservation_and_consumption_lifecycle():
    manager = BudgetManager(global_limits={"max_ai_calls": 5})

    # Reserve 2 calls for microtopic A
    assert manager.reserve("topic-A", "ai_calls", 2) is True
    assert manager._dimension_reservations.get("ai_calls") == 2

    # Consuming 1 call should reconcile reservation from 2 to 1 and add 1 to usage
    manager.consume("topic-A", "ai_calls", 1)
    assert manager._reservations.get("topic-A:ai_calls") == 1
    assert manager.global_usage.ai_calls == 1

    # Releasing remaining 1 reservation
    manager.release("topic-A", "ai_calls", 1)
    assert manager._reservations.get("topic-A:ai_calls") == 0
    assert manager._dimension_reservations.get("ai_calls") == 0
    assert manager.global_usage.ai_calls == 1


def test_p0_priority_pool_reserve_protection():
    # 4 total calls, with 2 calls reserved strictly for P0
    manager = BudgetManager(global_limits={"max_ai_calls": 4, "p0_reserved_calls": 2})

    # 1st P1 call: ok (4 - 1 = 3 >= 2)
    can_exec1, _ = manager.can_execute("t1", priority="P1")
    assert can_exec1 is True
    manager.consume("t1", "ai_calls", 1)

    # 2nd P1 call: ok (3 - 1 = 2 >= 2)
    can_exec2, _ = manager.can_execute("t2", priority="P1")
    assert can_exec2 is True
    manager.consume("t2", "ai_calls", 1)

    # 3rd P1 call: rejected! Only 2 calls left and they are reserved for P0
    can_exec3, reason3 = manager.can_execute("t3", priority="P1")
    assert can_exec3 is False
    assert reason3 == "RESERVED_FOR_P0"

    # P0 call: ALLOWED! P0 can use the reserved pool
    can_exec_p0, reason_p0 = manager.can_execute("t-critical", priority="P0")
    assert can_exec_p0 is True
    assert reason_p0 == "PROCEED"


def test_authorize_emits_structured_budget_trace_on_exhaustion():
    manager = BudgetManager(global_limits={"max_ai_calls": 1})
    manager.consume("t0", "ai_calls", 1)

    authorized, reason, skip_record = manager.authorize("t-skipped", priority="P2", estimated_calls=1, run_id="run-123")
    assert authorized is False
    assert reason == "GLOBAL_AI_CALL_BUDGET_EXHAUSTED"
    assert skip_record is not None
    assert skip_record.status == "BUDGET_SKIPPED"

    trace = skip_record.details.get("budget_trace", {})
    assert trace["pool"] == "P2"
    assert trace["dimension"] == "ai_calls"
    assert trace["limit"] == 1
    assert trace["allocated"] == 1
    assert trace["remaining"] == 0
    assert trace["required"] == 1
