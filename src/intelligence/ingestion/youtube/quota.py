"""YouTube API quota accounting and rate limit protection."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass
class YouTubeQuotaTracker:
    """Tracks YouTube Data API v3 quota usage and protects against uncontrolled consumption."""

    max_units_per_run: int = 2500
    youtube_requests: int = 0
    youtube_units: int = 0
    youtube_failures: int = 0
    youtube_rate_limit_events: int = 0
    youtube_last_success: str | None = None
    youtube_last_failure: str | None = None
    quota_exceeded: bool = False

    def can_spend(self, units: int = 1) -> bool:
        """Check if request units are within quota limit."""
        if self.quota_exceeded:
            return False
        return (self.youtube_units + units) <= self.max_units_per_run

    def record_success(self, units: int = 1) -> None:
        """Record successful request and quota units."""
        self.youtube_requests += 1
        self.youtube_units += units
        self.youtube_last_success = datetime.now(UTC).isoformat()

    def record_failure(self, is_rate_limit: bool = False, is_quota_exceeded: bool = False) -> None:
        """Record failed request, rate-limit, or quota exhaustion."""
        self.youtube_requests += 1
        self.youtube_failures += 1
        self.youtube_last_failure = datetime.now(UTC).isoformat()
        if is_rate_limit:
            self.youtube_rate_limit_events += 1
        if is_quota_exceeded:
            self.quota_exceeded = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Default shared instance
default_quota_tracker = YouTubeQuotaTracker()
