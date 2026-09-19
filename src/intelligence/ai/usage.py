"""Token counting, usage tracking, and cost estimation for AI provider interactions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Pricing per 1,000,000 tokens (USD)
DEFAULT_MODEL_PRICING: dict[str, dict[str, float]] = {
    "gemini-2.5-flash": {"input_per_million": 0.075, "output_per_million": 0.30},
    "gemini-1.5-flash": {"input_per_million": 0.075, "output_per_million": 0.30},
    "gemini-2.5-pro": {"input_per_million": 1.25, "output_per_million": 5.00},
    "gemini-1.5-pro": {"input_per_million": 1.25, "output_per_million": 5.00},
    "default": {"input_per_million": 0.10, "output_per_million": 0.40},
}


@dataclass(frozen=True)
class TokenUsage:
    """Detailed token usage and accounting metrics for an AI call."""

    prompt_tokens: int = 0
    candidate_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "candidate_tokens": self.candidate_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
        }

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            candidate_tokens=self.candidate_tokens + other.candidate_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            estimated_cost_usd=self.estimated_cost_usd + other.estimated_cost_usd,
        )


def calculate_cost(
    prompt_tokens: int,
    candidate_tokens: int,
    model: str = "gemini-2.5-flash",
    custom_pricing: dict[str, dict[str, float]] | None = None,
) -> float:
    """Calculate estimated cost in USD based on model pricing."""
    pricing_map = custom_pricing or DEFAULT_MODEL_PRICING
    pricing = pricing_map.get(model) or pricing_map.get("default", {"input_per_million": 0.10, "output_per_million": 0.40})
    cost_input = (prompt_tokens / 1_000_000.0) * pricing["input_per_million"]
    cost_output = (candidate_tokens / 1_000_000.0) * pricing["output_per_million"]
    return round(cost_input + cost_output, 6)


def estimate_tokens(text: str, safety_margin_percent: int = 15) -> int:
    """Fast deterministic token estimation with configurable safety margin."""
    if not text:
        return 0
    words = len(text.split())
    char_estimate = max(1, len(text) // 4)
    base = max(int(words * 1.25), char_estimate)
    margin = int(base * (safety_margin_percent / 100.0))
    return base + margin


def count_tokens_native(text: str, client: Any | None = None) -> int:
    """Return provider native token count if client available, otherwise deterministic estimate."""
    if client and hasattr(client, "count_tokens"):
        try:
            res = client.count_tokens(text)
            if hasattr(res, "total_tokens"):
                return int(res.total_tokens)
            if isinstance(res, int):
                return res
        except Exception:
            pass
    return estimate_tokens(text, safety_margin_percent=0)


@dataclass
class TokenAccountingRecord:
    """Tracks preflight estimate vs actual usage with mismatch diagnostics."""

    call_id: str
    micro_topic_id: str
    estimated_input_tokens: int = 0
    actual_input_tokens: int = 0
    estimated_output_tokens: int = 0
    actual_output_tokens: int = 0
    total_tokens: int = 0
    input_mismatch: int = 0
    output_mismatch: int = 0
    safety_margin_percent: int = 15

    @classmethod
    def create(
        cls,
        call_id: str,
        micro_topic_id: str,
        estimated_input: int,
        actual_input: int,
        estimated_output: int = 0,
        actual_output: int = 0,
        safety_margin_percent: int = 15,
    ) -> TokenAccountingRecord:
        total = actual_input + actual_output
        return cls(
            call_id=call_id,
            micro_topic_id=micro_topic_id,
            estimated_input_tokens=estimated_input,
            actual_input_tokens=actual_input,
            estimated_output_tokens=estimated_output,
            actual_output_tokens=actual_output,
            total_tokens=total,
            input_mismatch=actual_input - estimated_input,
            output_mismatch=actual_output - estimated_output,
            safety_margin_percent=safety_margin_percent,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "micro_topic_id": self.micro_topic_id,
            "estimated_input_tokens": self.estimated_input_tokens,
            "actual_input_tokens": self.actual_input_tokens,
            "estimated_output_tokens": self.estimated_output_tokens,
            "actual_output_tokens": self.actual_output_tokens,
            "total_tokens": self.total_tokens,
            "input_mismatch": self.input_mismatch,
            "output_mismatch": self.output_mismatch,
            "safety_margin_percent": self.safety_margin_percent,
        }


@dataclass
class CumulativeUsageTracker:
    """Cumulative usage aggregator across all pipeline AI interactions."""

    records: list[TokenAccountingRecord] = None  # type: ignore[assignment]
    total_estimated_input: int = 0
    total_actual_input: int = 0
    total_estimated_output: int = 0
    total_actual_output: int = 0
    total_tokens: int = 0

    def __post_init__(self) -> None:
        if self.records is None:
            self.records = []

    def record_call(
        self,
        call_id: str,
        micro_topic_id: str,
        estimated_input: int,
        actual_input: int,
        estimated_output: int = 0,
        actual_output: int = 0,
    ) -> TokenAccountingRecord:
        rec = TokenAccountingRecord.create(
            call_id=call_id,
            micro_topic_id=micro_topic_id,
            estimated_input=estimated_input,
            actual_input=actual_input,
            estimated_output=estimated_output,
            actual_output=actual_output,
        )
        self.records.append(rec)
        self.total_estimated_input += estimated_input
        self.total_actual_input += actual_input
        self.total_estimated_output += estimated_output
        self.total_actual_output += actual_output
        self.total_tokens += rec.total_tokens
        return rec

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_calls": len(self.records),
            "total_estimated_input_tokens": self.total_estimated_input,
            "actual_input_tokens": self.total_actual_input,
            "estimated_output_tokens": self.total_estimated_output,
            "actual_output_tokens": self.total_actual_output,
            "total_tokens": self.total_tokens,
            "records": [r.to_dict() for r in self.records],
        }


@dataclass(frozen=True)
class AIUsage:
    """Normalized provider-specific usage metrics."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    thought_tokens: int = 0
    tool_tokens: int = 0
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cached_tokens": self.cached_tokens,
            "thought_tokens": self.thought_tokens,
            "tool_tokens": self.tool_tokens,
            "latency_ms": self.latency_ms,
        }
