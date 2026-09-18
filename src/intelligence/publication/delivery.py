"""Delivery state machine and independent persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


class DeliveryState:
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    ATTEMPTED = "ATTEMPTED"
    DELIVERY_CONFIRMED = "DELIVERY_CONFIRMED"
    DELIVERY_FAILED = "DELIVERY_FAILED"
    QUALITY_REVIEW_REQUIRED = "QUALITY_REVIEW_REQUIRED"
    SKIPPED_DRY_RUN = "SKIPPED_DRY_RUN"


@dataclass
class DeliveryRecord:
    edition_key: str
    run_id: str
    delivery_status: str = DeliveryState.NOT_ATTEMPTED
    recipients: tuple[str, ...] = ()
    attempted_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    confirmed_at: str | None = None
    error_message: str | None = None
    retry_count: int = 0

    def confirm(self) -> None:
        self.delivery_status = DeliveryState.DELIVERY_CONFIRMED
        self.confirmed_at = datetime.now(UTC).isoformat()

    def fail(self, error: str) -> None:
        self.delivery_status = DeliveryState.DELIVERY_FAILED
        self.error_message = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "edition_key": self.edition_key,
            "run_id": self.run_id,
            "delivery_status": self.delivery_status,
            "recipients": list(self.recipients),
            "attempted_at": self.attempted_at,
            "confirmed_at": self.confirmed_at,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
        }
