"""Token budgeting, preflight estimation, reservation, and accounting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .usage import estimate_tokens


@dataclass
class TokenBudgetManager:
    """Manages preflight token reservations and post-call consumption against budget."""

    max_edition_tokens: int = 50_000
    max_microtopic_tokens: int = 4_000
    p0_reserve_tokens: int = 10_000
    consumed_tokens: int = 0
    _topic_usage: dict[str, int] = field(default_factory=dict)
    _reservations: dict[str, int] = field(default_factory=dict)

    def estimate_tokens(self, text: str) -> int:
        return estimate_tokens(text)

    def count_tokens(self, text: str) -> int:
        """Heuristic or SDK token counting."""
        return estimate_tokens(text)

    def authorize(self, topic_id: str, estimated_tokens: int, priority: int = 5) -> tuple[bool, str]:
        """Authorize token budget for a topic before AI generation."""
        # Enforce micro-topic token cap
        current_topic = self._topic_usage.get(topic_id, 0)
        if current_topic + estimated_tokens > self.max_microtopic_tokens:
            return False, "MICROTOPIC_BUDGET_EXCEEDED"

        # Check total remaining budget
        remaining = self.max_edition_tokens - self.consumed_tokens - sum(self._reservations.values())
        if priority < 8 and remaining <= self.p0_reserve_tokens:
            return False, "P0_RESERVE_RESTRICTED"

        if remaining < estimated_tokens:
            return False, "GLOBAL_BUDGET_EXCEEDED"

        self._reservations[topic_id] = estimated_tokens
        return True, "AUTHORIZED"

    def consume(self, topic_id: str, actual_tokens: int) -> None:
        """Record actual tokens consumed and release reservation."""
        self._reservations.pop(topic_id, None)
        self.consumed_tokens += actual_tokens
        self._topic_usage[topic_id] = self._topic_usage.get(topic_id, 0) + actual_tokens

    def release_reservation(self, topic_id: str) -> None:
        self._reservations.pop(topic_id, None)

    def snapshot(self) -> dict[str, Any]:
        return {
            "max_edition_tokens": self.max_edition_tokens,
            "max_microtopic_tokens": self.max_microtopic_tokens,
            "p0_reserve_tokens": self.p0_reserve_tokens,
            "consumed_tokens": self.consumed_tokens,
            "active_reservations": sum(self._reservations.values()),
            "topics": dict(self._topic_usage),
        }
