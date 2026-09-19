"""Authoritative AIProvider protocol and BatchAIProvider adapter."""

from __future__ import annotations

from typing import Any, Protocol



class AIProvider(Protocol):
    """Authoritative protocol for intelligence AI providers."""

    def analyze_micro_topic(
        self,
        item: dict[str, Any],
        profile: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Analyze a micro-topic against bounded evidence and return normalized analysis."""
        ...

    def analyze(
        self,
        context: Any,
        contract: Any = None,
    ) -> dict[str, Any]:
        """Analyze a ContextPacket under the given analysis contract."""
        ...



class BatchAIProvider:
    """Batch API adapter for asynchronous, non-urgent evaluations or historical processing."""

    def __init__(self, key: str = "", model: str = "gemini-2.5-flash") -> None:
        self.key = key
        self.model = model
        self.queue: list[dict[str, Any]] = []

    def submit_batch(self, requests: list[dict[str, Any]]) -> str:
        batch_id = f"batch-{len(self.queue) + 1}"
        self.queue.extend(requests)
        return batch_id

    def get_status(self, batch_id: str) -> str:
        return "COMPLETED"

    def retrieve_results(self, batch_id: str) -> list[dict[str, Any]]:
        return []
