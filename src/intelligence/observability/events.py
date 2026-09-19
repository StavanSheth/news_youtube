"""Structured event telemetry emitter for intelligence pipeline stages."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from .logging import mask_secrets

LOGGER = logging.getLogger("intelligence.events")

PIPELINE_EVENTS = {
    "source_validation_started",
    "source_validation_completed",
    "source_failed",
    "source_quarantined",
    "ingestion_started",
    "ingestion_completed",
    "rag_index_started",
    "rag_index_completed",
    "rag_retrieval_started",
    "rag_retrieval_completed",
    "ai_call_started",
    "ai_call_completed",
    "ai_call_skipped_budget",
    "theme_execution_started",
    "theme_execution_completed",
    "theme_execution_failed",
}


def emit_pipeline_event(
    event_name: str,
    payload: dict[str, Any] | None = None,
    level: int = logging.INFO,
) -> dict[str, Any]:
    """Emit a sanitized structured event record across telemetry channels."""
    now_iso = datetime.now(UTC).isoformat()
    raw_payload = payload or {}

    # Sanitize and redact any secrets
    sanitized: dict[str, Any] = {}
    for k, v in raw_payload.items():
        if isinstance(v, str):
            sanitized[k] = mask_secrets(v)
        elif isinstance(v, dict):
            sanitized[k] = {sk: mask_secrets(sv) if isinstance(sv, str) else sv for sk, sv in v.items()}
        else:
            sanitized[k] = v

    record = {
        "event": event_name,
        "timestamp": now_iso,
        "payload": sanitized,
    }

    LOGGER.log(level, f"EVENT [{event_name}] {sanitized}", extra={"event_record": record})
    return record
