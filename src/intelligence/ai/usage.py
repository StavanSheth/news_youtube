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


def estimate_tokens(text: str) -> int:
    """Fast deterministic token estimation for prompt planning."""
    if not text:
        return 0
    words = len(text.split())
    char_estimate = max(1, len(text) // 4)
    return max(int(words * 1.25), char_estimate)

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
