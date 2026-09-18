"""Base protocols, request, and response contracts for AI providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .schemas import AnalysisOutput
from .usage import TokenUsage


@dataclass(frozen=True)
class AIRequest:
    """Standardized request envelope for AI generation."""

    micro_topic_id: str
    query: str = ""
    evidence: list[dict[str, Any]] = field(default_factory=list)
    profile: dict[str, Any] = field(default_factory=dict)
    item: dict[str, Any] = field(default_factory=dict)
    prompt_template: str = ""
    system_instruction: str = ""
    temperature: float = 0.2
    max_output_tokens: int = 4096


@dataclass(frozen=True)
class AIResponse:
    """Standardized response envelope from an AI provider invocation."""

    raw_text: str
    analysis: AnalysisOutput
    usage: TokenUsage = field(default_factory=TokenUsage)
    model: str = ""
    finish_reason: str = "STOP"
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis": self.analysis.to_normalized_dict(),
            "usage": self.usage.to_dict(),
            "model": self.model,
            "finish_reason": self.finish_reason,
            "latency_ms": self.latency_ms,
        }


class AIProvider(Protocol):
    """Authoritative protocol implemented by all AI providers."""

    def analyze_micro_topic(
        self,
        item: dict[str, Any],
        profile: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Analyze a micro-topic against bounded evidence and return normalized analysis."""
        ...
