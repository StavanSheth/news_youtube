"""Stable machine-readable error taxonomy across intelligence modules."""

from __future__ import annotations

from enum import StrEnum


class PipelineErrorCode(StrEnum):
    AUTH_FAILED = "AUTH_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    SCHEMA_ERROR = "SCHEMA_ERROR"
    STALE_SOURCE = "STALE_SOURCE"
    NO_CONTENT = "NO_CONTENT"
    QUARANTINED = "QUARANTINED"
    BUDGET_SKIPPED = "BUDGET_SKIPPED"
    RAG_INELIGIBLE = "RAG_INELIGIBLE"
    INVALID_AI_OUTPUT = "INVALID_AI_OUTPUT"
    NO_USABLE_SOURCE = "NO_USABLE_SOURCE"
    CONFIG_INVALID = "CONFIG_INVALID"


class PipelineError(Exception):
    """Base exception carrying structured machine-readable error code."""

    def __init__(self, code: PipelineErrorCode | str, message: str = "", details: dict | None = None) -> None:
        self.code = code.value if hasattr(code, "value") else str(code)
        self.message = message or self.code
        self.details = details or {}
        super().__init__(f"[{self.code}] {self.message}")
