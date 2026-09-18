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

    def reset(self) -> None:
        self.counters.clear()
        self.gauges.clear()
        self.timers.clear()


# Default global metrics instance
default_metrics = MetricsRegistry()
