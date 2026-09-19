"""Tests for Provider-aware budget limits, rate limiting, and reservation lifecycle."""

from __future__ import annotations

from intelligence.budgets.manager import BudgetManager, ProviderBudgetConfig


def test_provider_budget_rpm_sliding_window():
    cfg = ProviderBudgetConfig(
        provider="gemini",
        tier="FREE",
        rpm=2,
        safety_margin_percent=0,
    )
    bm = BudgetManager(provider_budget=cfg)

    # 1st call ok
    ok1, reason1 = bm.can_execute("topic-1", estimated_calls=1)
    assert ok1 is True
    bm.record_provider_call(tokens=100)

    # 2nd call ok
    ok2, reason2 = bm.can_execute("topic-1", estimated_calls=1)
    assert ok2 is True
    bm.record_provider_call(tokens=100)

    # 3rd call within the same minute should be rejected due to RPM
    ok3, reason3 = bm.can_execute("topic-1", estimated_calls=1)
    assert ok3 is False
    assert reason3 == "PROVIDER_RPM_EXHAUSTED"


def test_provider_budget_tpm_limit():
    cfg = ProviderBudgetConfig(
        provider="gemini",
        tier="FREE",
        input_tpm=1000,
        safety_margin_percent=10,  # effective cap = 900
    )
    bm = BudgetManager(provider_budget=cfg)

    # Requesting 800 tokens should be allowed
    ok1, _ = bm.can_execute("topic-1", estimated_tokens=800)
    assert ok1 is True
    bm.record_provider_call(tokens=800)

    # Requesting 200 tokens now puts it at 1000 > 900 effective cap
    ok2, reason2 = bm.can_execute("topic-1", estimated_tokens=200)
    assert ok2 is False
    assert reason2 == "PROVIDER_TPM_EXHAUSTED"


def test_provider_budget_rpd_limit():
    cfg = ProviderBudgetConfig(
        provider="gemini",
        tier="FREE",
        rpd=3,
        safety_margin_percent=0,
    )
    bm = BudgetManager(provider_budget=cfg)

    for _ in range(3):
        ok, _ = bm.can_execute("topic-1", estimated_calls=1)
        assert ok is True
        bm.record_provider_call(tokens=50)

    ok_excess, reason = bm.can_execute("topic-1", estimated_calls=1)
    assert ok_excess is False
    assert reason == "PROVIDER_RPD_EXHAUSTED"


def test_provider_max_run_limits():
    cfg = ProviderBudgetConfig(
        provider="gemini",
        tier="PAID",
        max_run_calls=2,
        max_run_input_tokens=500,
    )
    bm = BudgetManager(provider_budget=cfg)

    # First call ok
    auth1, _, _ = bm.authorize("topic-1", estimated_calls=1, estimated_tokens=300)
    assert auth1 is True
    bm.consume("topic-1", "ai_calls", 1)
    bm.consume("topic-1", "input_tokens", 300)

    # Second call exceeds max_run_input_tokens (300 + 300 > 500)
    auth2, reason2, record2 = bm.authorize("topic-1", estimated_calls=1, estimated_tokens=300)
    assert auth2 is False
    assert reason2 == "PROVIDER_RUN_TOKENS_EXHAUSTED"
    assert record2 is not None


def test_reservation_and_release_on_failure():
    bm = BudgetManager(
        global_limits={"max_ai_calls": 2, "max_input_tokens": 1000},
        micro_topic_limits={"topic-1": {"max_ai_calls": 1, "max_input_tokens": 500}},
    )

    # Authorize reserves resources
    auth, _, _ = bm.authorize("topic-1", estimated_calls=1, estimated_tokens=400)
    assert auth is True
    assert bm._dimension_reservations["ai_calls"] == 1
    assert bm._dimension_reservations["input_tokens"] == 400

    # Second attempt for same topic fails because of active reservation
    auth2, reason2, _ = bm.authorize("topic-1", estimated_calls=1, estimated_tokens=400)
    assert auth2 is False
    assert reason2 == "MICRO_TOPIC_AI_CALL_LIMIT_EXCEEDED"

    # Call fails in execution -> release reservation
    bm.release("topic-1", "ai_calls", 1)
    bm.release("topic-1", "input_tokens", 400)

    assert bm._dimension_reservations["ai_calls"] == 0
    assert bm._dimension_reservations["input_tokens"] == 0

    # Now topic-1 can be authorized again
    auth3, reason3, _ = bm.authorize("topic-1", estimated_calls=1, estimated_tokens=400)
    assert auth3 is True
    assert reason3 == "AUTHORIZED"
