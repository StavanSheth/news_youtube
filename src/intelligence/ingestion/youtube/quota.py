"""YouTube API quota accounting and rate limit protection."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass
class YouTubeQuotaTracker:
    """Tracks YouTube Data API v3 quota usage, reserves quota units, and trips circuit breaker on repeated failure."""

    max_units_per_run: int = 2500
    daily_quota_limit: int = 10000
    youtube_requests: int = 0
    youtube_units: int = 0
    youtube_failures: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    status_429_responses: int = 0
    youtube_rate_limit_events: int = 0
    daily_usage_estimate: int = 0
    circuit_breaker_tripped: bool = False
    circuit_breaker_threshold: int = 3
    _consecutive_failures: int = 0
    _reserved_units: int = 0
    youtube_last_success: str | None = None
    youtube_last_failure: str | None = None
    quota_exceeded: bool = False

    def can_spend(self, units: int = 1) -> bool:
        """Check if request units are within quota limit and circuit breaker is untripped."""
        if self.quota_exceeded or self.circuit_breaker_tripped:
            return False
        return (self.youtube_units + self._reserved_units + units) <= self.max_units_per_run

    def reserve(self, units: int = 1) -> bool:
        """Reserve quota units before making network request."""
        if not self.can_spend(units):
            return False
        self._reserved_units += units
        return True

    def release(self, units: int = 1) -> None:
        """Release reserved quota units on failure or cancellation."""
        self._reserved_units = max(0, self._reserved_units - units)

    def consume(self, units: int = 1) -> None:
        """Record successful call, release reservation, and consume actual units."""
        self.release(units)
        self.record_success(units=units)

    def record_success(self, units: int = 1) -> None:
        """Record successful request and quota units."""
        self.youtube_requests += 1
        self.successful_requests += 1
        self.youtube_units += units
        self.daily_usage_estimate += units
        self._consecutive_failures = 0
        self.youtube_last_success = datetime.now(UTC).isoformat()

    def record_failure(self, is_rate_limit: bool = False, is_quota_exceeded: bool = False, is_429: bool = False) -> None:
        """Record failed request, rate-limit, or quota exhaustion with circuit breaker trip."""
        self.youtube_requests += 1
        self.youtube_failures += 1
        self.failed_requests += 1
        self._consecutive_failures += 1
        self.youtube_last_failure = datetime.now(UTC).isoformat()

        if is_rate_limit or is_429:
            self.youtube_rate_limit_events += 1
            self.status_429_responses += 1

        if is_quota_exceeded or self._consecutive_failures >= self.circuit_breaker_threshold:
            self.quota_exceeded = True
            self.circuit_breaker_tripped = True

    def record_request(self, success: bool = True, status_code: int = 200, units: int = 1) -> None:
        """Convenience method recording request by success and HTTP status code."""
        if success and status_code < 400:
            self.record_success(units=units)
        else:
            self.record_failure(is_429=(status_code == 429), is_quota_exceeded=(status_code == 403))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["requests"] = self.youtube_requests
        data["quota_units"] = self.youtube_units
        return data


# Default shared instance
default_quota_tracker = YouTubeQuotaTracker()
