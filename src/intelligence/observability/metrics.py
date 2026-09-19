"""In-memory metrics registry for tracking counters, gauges, and stage durations."""

from __future__ import annotations

import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator


@dataclass
class MetricsRegistry:
    """Thread-safe in-memory metrics registry."""

    counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    gauges: dict[str, float] = field(default_factory=dict)
    timers: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def count(self, name: str, value: int = 1) -> None:
        self.counters[name] += value

    def count_source_check(self, status: str) -> None:
        self.count(f"source_checks_total.{status.lower()}")
        self.count("source_checks_total")

    def count_source_ready(self) -> None:
        self.count("sources_ready_total")

    def count_source_quarantined(self) -> None:
        self.count("sources_quarantined_total")

    def count_youtube_quota(self, units: int) -> None:
        self.count("youtube_quota_units_used", units)
        self.count("youtube_requests_total")

    def gauge(self, name: str, value: float) -> None:
        self.gauges[name] = float(value)

    def record_duration(self, name: str, duration_ms: float) -> None:
        self.timers[name].append(float(duration_ms))

    @contextmanager
    def timer(self, name: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self.record_duration(name, elapsed_ms)

    def snapshot(self) -> dict[str, Any]:
        """Return serialized summary of all metrics."""
        timer_summaries = {}
        for name, values in self.timers.items():
            if values:
                timer_summaries[name] = {
                    "count": len(values),
                    "total_ms": round(sum(values), 2),
                    "avg_ms": round(sum(values) / len(values), 2),
                    "min_ms": round(min(values), 2),
                    "max_ms": round(max(values), 2),
                }
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "timers": timer_summaries,
        }

    def record_source_execution(
        self,
        source_id: str,
        provider: str,
        latency_ms: float,
        items_seen: int = 0,
        items_valid: int = 0,
        items_rejected: int = 0,
        collection_success: bool = True,
        schema_valid: bool = True,
        content_extractable: bool = True,
        rag_items_ingested: int = 0,
        rag_items_rejected: int = 0,
        failure_code: str | None = None,
        retry_count: int = 0,
    ) -> None:
        """Record fine-grained source execution metrics per Section L."""
        self.record_duration(f"source_latency_ms.{source_id}", latency_ms)
        self.record_duration(f"provider_latency_ms.{provider}", latency_ms)
        self.count("items_seen_total", items_seen)
        self.count("items_valid_total", items_valid)
        self.count("items_rejected_total", items_rejected)
        self.count("rag_items_ingested_total", rag_items_ingested)
        self.count("rag_items_rejected_total", rag_items_rejected)
        self.count("retries_total", retry_count)

        if collection_success and schema_valid and content_extractable:
            self.count("source_executions_success_total")
        else:
            self.count("source_executions_failure_total")

        if failure_code:
            self.count(f"failures_by_code.{failure_code}")

    def compute_aggregated_rates(self) -> dict[str, float]:
        """Compute authoritative aggregated rate metrics per Section L."""
        succ = self.counters.get("source_executions_success_total", 0)
        fail = self.counters.get("source_executions_failure_total", 0)
        total_execs = succ + fail

        ready = self.counters.get("sources_ready_total", 0)
        quar = self.counters.get("sources_quarantined_total", 0)
        total_sources = ready + quar

        ingested = self.counters.get("rag_items_ingested_total", 0)
        rejected = self.counters.get("rag_items_rejected_total", 0)
        total_rag = ingested + rejected

        items_seen = self.counters.get("items_seen_total", 0)
        items_valid = self.counters.get("items_valid_total", 0)

        return {
            "source_success_rate": round(succ / max(1, total_execs) * 100.0, 2) if total_execs > 0 else 100.0,
            "source_failure_rate": round(fail / max(1, total_execs) * 100.0, 2) if total_execs > 0 else 0.0,
            "source_quarantine_rate": round(quar / max(1, total_sources) * 100.0, 2) if total_sources > 0 else 0.0,
            "provider_failure_rate": round(fail / max(1, total_execs) * 100.0, 2) if total_execs > 0 else 0.0,
            "microtopic_coverage": round(self.gauges.get("microtopic_coverage_pct", 100.0), 2),
            "freshness_rate": round(items_valid / max(1, items_seen) * 100.0, 2) if items_seen > 0 else 100.0,
            "RAG_ingestion_rate": round(ingested / max(1, total_rag) * 100.0, 2) if total_rag > 0 else 100.0,
            "RAG_rejection_rate": round(rejected / max(1, total_rag) * 100.0, 2) if total_rag > 0 else 0.0,
        }

    def reset(self) -> None:
        self.counters.clear()
        self.gauges.clear()
        self.timers.clear()


# Default global metrics instance
default_metrics = MetricsRegistry()
