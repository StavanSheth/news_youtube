"""Centralized clock abstraction eliminating scattered datetime.now() calls."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from zoneinfo import ZoneInfo


class Clock(Protocol):
    """Protocol for time sources, supporting injection for deterministic testing."""

    def now_utc(self) -> datetime:
        """Return the current UTC datetime."""
        ...

    def now_local(self, timezone: str = "Asia/Kolkata") -> datetime:
        """Return the current localized datetime."""
        ...


class SystemClock:
    """Default system wall-clock implementation."""

    def now_utc(self) -> datetime:
        return datetime.now(UTC)

    def now_local(self, timezone: str = "Asia/Kolkata") -> datetime:
        return datetime.now(ZoneInfo(timezone))


class FixedClock:
    """Deterministic frozen clock for testing and replay."""

    def __init__(self, fixed_time: datetime) -> None:
        if fixed_time.tzinfo is None:
            self._fixed = fixed_time.replace(tzinfo=UTC)
        else:
            self._fixed = fixed_time.astimezone(UTC)

    def now_utc(self) -> datetime:
        return self._fixed

    def now_local(self, timezone: str = "Asia/Kolkata") -> datetime:
        return self._fixed.astimezone(ZoneInfo(timezone))


_GLOBAL_CLOCK: Clock = SystemClock()


def get_clock() -> Clock:
    """Get the active global clock instance."""
    return _GLOBAL_CLOCK


def set_clock(clock: Clock) -> None:
    """Set the active global clock (primarily for test fixtures)."""
    global _GLOBAL_CLOCK
    _GLOBAL_CLOCK = clock


def now_utc() -> datetime:
    """Return current UTC time using the active clock."""
    return _GLOBAL_CLOCK.now_utc()


def now_local(timezone: str = "Asia/Kolkata") -> datetime:
    """Return current localized time using the active clock."""
    return _GLOBAL_CLOCK.now_local(timezone)
