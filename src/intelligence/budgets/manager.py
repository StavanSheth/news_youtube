"""Authoritative Budget Manager enforcing hard ceilings, priorities, and audit skips."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ProviderBudgetConfig:
    """Configurable provider-aware quota limits (e.g. Gemini RPM, TPM, RPD)."""

    provider: str = "gemini"
    tier: str = "FREE"
    rpm: int | None = None
    input_tpm: int | None = None
    output_tpm: int | None = None
    rpd: int | None = None
    safety_margin_percent: int = 20
    max_run_calls: int | None = None
    max_run_input_tokens: int | None = None
    max_run_output_tokens: int | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> ProviderBudgetConfig:
        if not data:
            return cls()
        return cls(
            provider=str(data.get("provider", "gemini")),
            tier=str(data.get("tier", "FREE")),
            rpm=data.get("rpm"),
            input_tpm=data.get("input_tpm"),
            output_tpm=data.get("output_tpm"),
            rpd=data.get("rpd"),
            safety_margin_percent=int(data.get("safety_margin_percent", 20)),
            max_run_calls=data.get("max_run_calls"),
            max_run_input_tokens=data.get("max_run_input_tokens"),
            max_run_output_tokens=data.get("max_run_output_tokens"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "tier": self.tier,
            "rpm": self.rpm,
            "input_tpm": self.input_tpm,
            "output_tpm": self.output_tpm,
            "rpd": self.rpd,
            "safety_margin_percent": self.safety_margin_percent,
            "max_run_calls": self.max_run_calls,
            "max_run_input_tokens": self.max_run_input_tokens,
            "max_run_output_tokens": self.max_run_output_tokens,
        }


@dataclass
class BudgetLimits:
    source_items: int = 100
    rag_items: int = 10
    context_chunks: int = 20
    context_chars: int = 25000
    input_tokens: int = 30000
    output_tokens: int = 8000
    ai_calls: int = 30
    total_tokens: int = 40000
    retries: int = 5


@dataclass
class BudgetUsage:
    source_items: int = 0
    rag_items: int = 0
    context_chunks: int = 0
    context_chars: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    ai_calls: int = 0
    total_tokens: int = 0
    retries: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "source_items": self.source_items,
            "rag_items": self.rag_items,
            "context_chunks": self.context_chunks,
            "context_chars": self.context_chars,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "ai_calls": self.ai_calls,
            "total_tokens": self.total_tokens,
            "retries": self.retries,
        }


@dataclass
class BudgetSkipRecord:
    micro_topic_id: str
    status: str = "BUDGET_SKIPPED"
    reason: str = "BUDGET_EXHAUSTED"
    priority: str = "P2"
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "micro_topic_id": self.micro_topic_id,
            "status": self.status,
            "reason": self.reason,
            "priority": self.priority,
            "details": self.details,
        }

    def __contains__(self, item: str) -> bool:
        return item in self.reason or item in self.status

    def __str__(self) -> str:
        return f"{self.status}: {self.reason}"


class BudgetManager:
    """Authoritative controller enforcing budget limits across global run and micro-topic jobs."""

    def __init__(
        self,
        global_limits: dict[str, Any] | None = None,
        micro_topic_limits: dict[str, dict[str, Any]] | None = None,
        provider_budget: ProviderBudgetConfig | dict[str, Any] | None = None,
    ) -> None:
        self.config = dict(global_limits or {})
        pb = provider_budget if provider_budget is not None else self.config.get("provider_budget")
        if isinstance(pb, ProviderBudgetConfig):
            self.provider_budget = pb
        else:
            self.provider_budget = ProviderBudgetConfig.from_mapping(pb)
        self.global_limits = self._parse_limits(global_limits or {})
        self.micro_topic_limits = {
            k: self._parse_limits(v) for k, v in (micro_topic_limits or {}).items()
        }
        self.global_usage = BudgetUsage()
        self.micro_topic_usage: dict[str, BudgetUsage] = {}
        self.skips: list[BudgetSkipRecord] = []
        self._reservations: dict[str, int] = {}
        self._dimension_reservations: dict[str, int] = {}
        self._call_timestamps: list[float] = []
        self._token_timestamps: list[tuple[float, int]] = []
        self._daily_calls: int = 0

    @staticmethod
    def _parse_limits(config: dict[str, Any]) -> BudgetLimits:
        ai_calls_val = config.get("max_ai_calls")
        if ai_calls_val is None:
            ai_calls_val = config.get("edition_max_ai_calls", 30)
        return BudgetLimits(
            source_items=int(config.get("max_source_items", 100)),
            rag_items=int(config.get("max_rag_items", 10)),
            context_chunks=int(config.get("max_context_chunks", 20)),
            context_chars=int(config.get("max_context_chars", config.get("max_retrieved_context_chars", 25000))),
            input_tokens=int(config.get("max_input_tokens", 30000)),
            output_tokens=int(config.get("max_output_tokens", 8000)),
            ai_calls=int(ai_calls_val),
            total_tokens=int(config.get("max_total_tokens", 40000)),
            retries=int(config.get("max_retries", 5)),
        )

    def _get_or_create_usage(self, micro_topic_id: str) -> BudgetUsage:
        if micro_topic_id not in self.micro_topic_usage:
            self.micro_topic_usage[micro_topic_id] = BudgetUsage()
        return self.micro_topic_usage[micro_topic_id]

    def check_provider_limits(
        self,
        estimated_calls: int = 1,
        estimated_tokens: int = 0,
        now: float | None = None,
    ) -> tuple[bool, str]:
        """Verify Level 1 provider quotas (Gemini RPM, TPM, RPD) with safety margin."""
        import time

        now_ts = now if now is not None else time.time()
        self._call_timestamps = [ts for ts in self._call_timestamps if now_ts - ts < 60.0]
        self._token_timestamps = [item for item in self._token_timestamps if now_ts - item[0] < 60.0]

        factor = max(0.1, 1.0 - (self.provider_budget.safety_margin_percent / 100.0))

        if self.provider_budget.rpm is not None:
            effective_rpm = max(1, int(self.provider_budget.rpm * factor))
            active_reserved = self._dimension_reservations.get("ai_calls", 0)
            if len(self._call_timestamps) + active_reserved + estimated_calls > effective_rpm:
                return False, "PROVIDER_RPM_EXHAUSTED"

        if self.provider_budget.input_tpm is not None:
            effective_tpm = max(1, int(self.provider_budget.input_tpm * factor))
            current_tokens = sum(t for _, t in self._token_timestamps)
            active_token_reserved = self._dimension_reservations.get("input_tokens", 0)
            if current_tokens + active_token_reserved + estimated_tokens > effective_tpm:
                return False, "PROVIDER_TPM_EXHAUSTED"

        if self.provider_budget.rpd is not None:
            if self._daily_calls + estimated_calls > self.provider_budget.rpd:
                return False, "PROVIDER_RPD_EXHAUSTED"

        if self.provider_budget.max_run_calls is not None:
            active_reserved = self._dimension_reservations.get("ai_calls", 0)
            if self.global_usage.ai_calls + active_reserved + estimated_calls > self.provider_budget.max_run_calls:
                return False, "PROVIDER_RUN_CALLS_EXHAUSTED"

        if self.provider_budget.max_run_input_tokens is not None:
            active_token_reserved = self._dimension_reservations.get("input_tokens", 0)
            if self.global_usage.input_tokens + active_token_reserved + estimated_tokens > self.provider_budget.max_run_input_tokens:
                return False, "PROVIDER_RUN_TOKENS_EXHAUSTED"

        return True, "PROCEED"

    def can_execute(
        self,
        micro_topic_id: str,
        priority: str = "P1",
        estimated_calls: int = 1,
        estimated_chars: int = 0,
        estimated_tokens: int = 0,
    ) -> tuple[bool, str]:
        """Check if execution can proceed under 5-level hierarchy and priority protection."""
        # Level 1: Provider budget
        provider_ok, provider_reason = self.check_provider_limits(
            estimated_calls=estimated_calls,
            estimated_tokens=estimated_tokens,
        )
        if not provider_ok:
            return False, provider_reason

        priority = priority.upper()
        p0_reserve = int(self.config.get("p0_reserved_calls", self.config.get("p0_reserve", 0)))
        reserved_calls = self._dimension_reservations.get("ai_calls", 0)

        # Level 2: Edition/run budget (AI calls)
        remaining_calls = self.global_limits.ai_calls - (self.global_usage.ai_calls + reserved_calls)
        if remaining_calls < estimated_calls:
            if priority == "P0" and remaining_calls >= 1:
                return True, "PROCEED"
            return False, "GLOBAL_AI_CALL_BUDGET_EXHAUSTED"

        # Check P0 reserve protection against P1/P2
        if p0_reserve > 0 and priority != "P0":
            if remaining_calls - estimated_calls < p0_reserve:
                return False, "RESERVED_FOR_P0"

        # Context chars check
        reserved_chars = self._dimension_reservations.get("context_chars", 0)
        if self.global_usage.context_chars + reserved_chars + estimated_chars > self.global_limits.context_chars:
            if priority != "P0":
                return False, "GLOBAL_CONTEXT_CHAR_BUDGET_EXHAUSTED"

        # Token ceiling check
        if estimated_tokens > 0:
            reserved_tokens = self._dimension_reservations.get("input_tokens", 0)
            if self.global_usage.input_tokens + reserved_tokens + estimated_tokens > self.global_limits.input_tokens:
                if priority != "P0":
                    return False, "GLOBAL_INPUT_TOKEN_BUDGET_EXHAUSTED"

        # Level 3: Micro-topic limits
        res_topic_calls = self._reservations.get(f"{micro_topic_id}:ai_calls", 0)
        res_topic_chars = self._reservations.get(f"{micro_topic_id}:context_chars", 0)
        res_topic_tokens = self._reservations.get(f"{micro_topic_id}:input_tokens", 0)

        if micro_topic_id in self.micro_topic_limits:
            limits = self.micro_topic_limits[micro_topic_id]
            usage = self._get_or_create_usage(micro_topic_id)
            if usage.ai_calls + res_topic_calls + estimated_calls > limits.ai_calls:
                return False, "MICRO_TOPIC_AI_CALL_LIMIT_EXCEEDED"
            if estimated_chars and usage.context_chars + res_topic_chars + estimated_chars > limits.context_chars:
                return False, "MICRO_TOPIC_CONTEXT_CHAR_LIMIT_EXCEEDED"
            if estimated_tokens and usage.input_tokens + res_topic_tokens + estimated_tokens > limits.input_tokens:
                return False, "MICRO_TOPIC_INPUT_TOKEN_LIMIT_EXCEEDED"

        max_per_topic = self.config.get("max_ai_calls_per_micro_topic")
        if max_per_topic is not None:
            usage = self._get_or_create_usage(micro_topic_id)
            if usage.ai_calls + res_topic_calls + estimated_calls > int(max_per_topic):
                return False, "MICRO_TOPIC_AI_CALL_LIMIT_EXCEEDED"

        return True, "PROCEED"

    def authorize(
        self,
        micro_topic_id: str,
        priority: str = "P1",
        estimated_calls: int = 1,
        estimated_chars: int = 0,
        estimated_tokens: int = 0,
        run_id: str = "",
    ) -> tuple[bool, str, BudgetSkipRecord | None]:
        """Authorize work BEFORE execution. If not allowed, automatically persist skip record."""
        can_run, reason = self.can_execute(
            micro_topic_id,
            priority=priority,
            estimated_calls=estimated_calls,
            estimated_chars=estimated_chars,
            estimated_tokens=estimated_tokens,
        )
        if not can_run:
            now_iso = datetime.now(UTC).isoformat()
            reserved_calls = self._dimension_reservations.get("ai_calls", 0)
            record = self.skip(
                micro_topic_id=micro_topic_id,
                reason=reason,
                priority=priority,
                details={
                    "run_id": run_id,
                    "timestamp": now_iso,
                    "requested_calls": estimated_calls,
                    "requested_chars": estimated_chars,
                    "requested_tokens": estimated_tokens,
                    "global_calls_used": self.global_usage.ai_calls,
                    "global_calls_limit": self.global_limits.ai_calls,
                    "budget_trace": {
                        "pool": priority,
                        "dimension": "ai_calls",
                        "limit": self.global_limits.ai_calls,
                        "allocated": self.global_usage.ai_calls + reserved_calls,
                        "remaining": max(0, self.global_limits.ai_calls - (self.global_usage.ai_calls + reserved_calls)),
                        "required": estimated_calls,
                    },
                },
            )
            return False, reason, record

        # Automatically record reservation upon authorization
        self.reserve(micro_topic_id, "ai_calls", estimated_calls)
        if estimated_chars > 0:
            self.reserve(micro_topic_id, "context_chars", estimated_chars)
        if estimated_tokens > 0:
            self.reserve(micro_topic_id, "input_tokens", estimated_tokens)

        return True, "AUTHORIZED", None

    def reserve(
        self,
        micro_topic_id: str,
        dimension: str,
        amount: int,
    ) -> bool:
        """Reserve budget units before starting an operation."""
        if amount <= 0:
            return True
        key = f"{micro_topic_id}:{dimension}"
        self._reservations[key] = self._reservations.get(key, 0) + amount
        self._dimension_reservations[dimension] = self._dimension_reservations.get(dimension, 0) + amount
        return True

    def release(
        self,
        micro_topic_id: str,
        dimension: str,
        amount: int,
    ) -> None:
        """Release unused reserved budget units."""
        if amount <= 0:
            return
        key = f"{micro_topic_id}:{dimension}"
        current = self._reservations.get(key, 0)
        released = min(current, amount)
        self._reservations[key] = max(0, current - released)
        self._dimension_reservations[dimension] = max(
            0, self._dimension_reservations.get(dimension, 0) - released
        )

    def consume(
        self,
        micro_topic_id: str,
        dimension: str,
        amount: int,
    ) -> None:
        """Record actual budget consumption and reconcile active reservations."""
        # Reconcile pending reservation if present
        key = f"{micro_topic_id}:{dimension}"
        if key in self._reservations:
            reserved = self._reservations[key]
            reconciled = min(reserved, amount)
            self._reservations[key] = max(0, reserved - reconciled)
            self._dimension_reservations[dimension] = max(
                0, self._dimension_reservations.get(dimension, 0) - reconciled
            )

        if hasattr(self.global_usage, dimension):
            current = getattr(self.global_usage, dimension)
            setattr(self.global_usage, dimension, current + amount)

        usage = self._get_or_create_usage(micro_topic_id)
        if hasattr(usage, dimension):
            current = getattr(usage, dimension)
            setattr(usage, dimension, current + amount)

        # Track provider window consumption
        import time
        now_ts = time.time()
        if dimension == "ai_calls":
            for _ in range(amount):
                self._call_timestamps.append(now_ts)
            self._daily_calls += amount
        elif dimension == "input_tokens":
            self._token_timestamps.append((now_ts, amount))

    def record_provider_call(self, tokens: int = 0, calls: int = 1) -> None:
        """Directly record a provider call against sliding windows."""
        import time
        now_ts = time.time()
        for _ in range(calls):
            self._call_timestamps.append(now_ts)
        self._daily_calls += calls
        if tokens > 0:
            self._token_timestamps.append((now_ts, tokens))

    def skip(
        self,
        micro_topic_id: str,
        reason: str,
        priority: str = "P2",
        details: dict[str, Any] | None = None,
    ) -> BudgetSkipRecord:
        """Record an explicit budget skip."""
        record = BudgetSkipRecord(
            micro_topic_id=micro_topic_id,
            status="BUDGET_SKIPPED",
            reason=reason,
            priority=priority,
            details=details or {},
        )
        self.skips.append(record)
        return record

    def snapshot(self) -> dict[str, Any]:
        """Return full budget audit snapshot."""
        return {
            "provider_budget": self.provider_budget.to_dict(),
            "provider_usage": {
                "active_rpm": len(self._call_timestamps),
                "active_tpm": sum(t for _, t in self._token_timestamps),
                "daily_calls": self._daily_calls,
            },
            "active_reservations": dict(self._dimension_reservations),
            "global_usage": self.global_usage.to_dict(),
            "global_limits": {
                k: getattr(self.global_limits, k)
                for k in (
                    "source_items", "rag_items", "context_chunks", "context_chars",
                    "input_tokens", "output_tokens", "ai_calls", "total_tokens", "retries",
                )
            },
            "micro_topic_usage": {k: v.to_dict() for k, v in self.micro_topic_usage.items()},
            "skips": [s.to_dict() for s in self.skips],
            "total_skips": len(self.skips),
        }
