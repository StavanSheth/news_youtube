"""Authoritative Budget Manager enforcing hard ceilings, priorities, and audit skips."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


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


class BudgetManager:
    """Authoritative controller enforcing budget limits across global run and micro-topic jobs."""

    def __init__(
        self,
        global_limits: dict[str, Any] | None = None,
        micro_topic_limits: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.config = dict(global_limits or {})
        self.global_limits = self._parse_limits(global_limits or {})
        self.micro_topic_limits = {
            k: self._parse_limits(v) for k, v in (micro_topic_limits or {}).items()
        }
        self.global_usage = BudgetUsage()
        self.micro_topic_usage: dict[str, BudgetUsage] = {}
        self.skips: list[BudgetSkipRecord] = []
        self._reservations: dict[str, dict[str, int]] = {}

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

    def can_execute(
        self,
        micro_topic_id: str,
        priority: str = "P1",
        estimated_calls: int = 1,
        estimated_chars: int = 0,
    ) -> tuple[bool, str]:
        """Check if execution can proceed under priority protection rules."""
        priority = priority.upper()
        # Check global AI calls
        remaining_calls = self.global_limits.ai_calls - self.global_usage.ai_calls
        if remaining_calls < estimated_calls:
            # P0 is protected if at least 1 call remains
            if priority == "P0" and remaining_calls >= 1:
                return True, "PROCEED"
            return False, "GLOBAL_AI_CALL_BUDGET_EXHAUSTED"

        # Check global context chars
        if self.global_usage.context_chars + estimated_chars > self.global_limits.context_chars:
            if priority != "P0":
                return False, "GLOBAL_CONTEXT_CHAR_BUDGET_EXHAUSTED"

        # Check micro-topic limits if configured
        if micro_topic_id in self.micro_topic_limits:
            limits = self.micro_topic_limits[micro_topic_id]
            usage = self._get_or_create_usage(micro_topic_id)
            if usage.ai_calls + estimated_calls > limits.ai_calls:
                return False, "MICRO_TOPIC_AI_CALL_LIMIT_EXCEEDED"
            if estimated_chars and usage.context_chars + estimated_chars > limits.context_chars:
                return False, "MICRO_TOPIC_CONTEXT_CHAR_LIMIT_EXCEEDED"

        max_per_topic = self.config.get("max_ai_calls_per_micro_topic")
        if max_per_topic is not None:
            usage = self._get_or_create_usage(micro_topic_id)
            if usage.ai_calls + estimated_calls > int(max_per_topic):
                return False, "MICRO_TOPIC_AI_CALL_LIMIT_EXCEEDED"

        return True, "PROCEED"

    def authorize(
        self,
        micro_topic_id: str,
        priority: str = "P1",
        estimated_calls: int = 1,
        estimated_chars: int = 0,
        run_id: str = "",
    ) -> tuple[bool, str, BudgetSkipRecord | None]:
        """Authorize work BEFORE execution. If not allowed, automatically persist skip record."""
        can_run, reason = self.can_execute(
            micro_topic_id,
            priority=priority,
            estimated_calls=estimated_calls,
            estimated_chars=estimated_chars,
        )
        if not can_run:
            now_iso = datetime.now(UTC).isoformat()
            record = self.skip(
                micro_topic_id=micro_topic_id,
                reason=reason,
                priority=priority,
                details={
                    "run_id": run_id,
                    "timestamp": now_iso,
                    "requested_calls": estimated_calls,
                    "requested_chars": estimated_chars,
                    "global_calls_used": self.global_usage.ai_calls,
                    "global_calls_limit": self.global_limits.ai_calls,
                },
            )
            return False, reason, record
        return True, "AUTHORIZED", None

    def reserve(
        self,
        micro_topic_id: str,
        dimension: str,
        amount: int,
    ) -> bool:
        """Reserve budget units before starting an operation."""
        key = f"{micro_topic_id}:{dimension}"
        self._reservations[key] = self._reservations.get(key, 0) + amount
        return True

    def release(
        self,
        micro_topic_id: str,
        dimension: str,
        amount: int,
    ) -> None:
        """Release unused reserved budget units."""
        key = f"{micro_topic_id}:{dimension}"
        if key in self._reservations:
            self._reservations[key] = max(0, self._reservations[key] - amount)

    def consume(
        self,
        micro_topic_id: str,
        dimension: str,
        amount: int,
    ) -> None:
        """Record actual budget consumption."""
        if hasattr(self.global_usage, dimension):
            current = getattr(self.global_usage, dimension)
            setattr(self.global_usage, dimension, current + amount)

        usage = self._get_or_create_usage(micro_topic_id)
        if hasattr(usage, dimension):
            current = getattr(usage, dimension)
            setattr(usage, dimension, current + amount)

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
