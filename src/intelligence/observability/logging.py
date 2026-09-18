"""Structured JSON logging with automatic secret masking and contextual fields."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

SECRET_PATTERNS = [
    re.compile(r"(api[_-]?key[\"'\s:=]+)([\w-]{16,})", re.IGNORECASE),
    re.compile(r"(password[\"'\s:=]+)([\w!@#$%^&*-]{6,})", re.IGNORECASE),
    re.compile(r"(bearer\s+)([\w._-]{16,})", re.IGNORECASE),
    re.compile(r"(secret[\"'\s:=]+)([\w-]{16,})", re.IGNORECASE),
]


def mask_secrets(text: str) -> str:
    """Mask credentials and secrets in text using regex patterns."""
    if not isinstance(text, str):
        return text
    masked = text
    for pattern in SECRET_PATTERNS:
        masked = pattern.sub(r"\1[REDACTED]", masked)
    return masked


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as structured JSON with contextual execution tags."""

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": mask_secrets(record.getMessage()),
        }

        # Include standard context fields if attached to the record
        for attr in ("run_id", "job_id", "stage", "micro_topic_id", "duration_ms", "status"):
            val = getattr(record, attr, None)
            if val is not None:
                data[attr] = val

        if record.exc_info:
            data["exception"] = mask_secrets(self.formatException(record.exc_info))

        return json.dumps(data, ensure_ascii=False)


def setup_structured_logging(level: int = logging.INFO) -> logging.Handler:
    """Configure and return root handler with structured JSON formatting."""
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredJsonFormatter())
    logging.root.setLevel(level)
    return handler
