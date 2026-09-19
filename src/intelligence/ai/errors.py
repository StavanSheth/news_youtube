"""Authoritative AI provider error hierarchy and classification."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCategory(StrEnum):
    """Categorized failure types for AI provider invocations."""

    AUTH_ERROR = "AUTH_ERROR"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    SCHEMA_ERROR = "SCHEMA_ERROR"
    SAFETY_BLOCK = "SAFETY_BLOCK"
    SERVER_ERROR = "SERVER_ERROR"
    UNKNOWN = "UNKNOWN"


RETRYABLE_CATEGORIES: set[ErrorCategory] = {
    ErrorCategory.RATE_LIMIT,
    ErrorCategory.TIMEOUT,
    ErrorCategory.NETWORK_ERROR,
    ErrorCategory.SERVER_ERROR,
}


class ProviderError(Exception):
    """Normalized exception encapsulating AI provider errors with retryability metadata."""

    def __init__(
        self,
        category: ErrorCategory,
        message: str,
        *,
        retryable: bool | None = None,
        status_code: int | None = None,
        cause: Exception | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.message = message
        self.retryable = retryable if retryable is not None else (category in RETRYABLE_CATEGORIES)
        self.status_code = status_code
        self.cause = cause
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "message": self.message,
            "retryable": self.retryable,
            "status_code": self.status_code,
            "details": self.details,
        }


def classify_gemini_error(exc: Exception) -> ProviderError:
    """Classify arbitrary exceptions into structured ProviderError."""
    if isinstance(exc, ProviderError):
        return exc

    err_str = str(exc).lower()
    exc_type = type(exc).__name__.lower()

    # Rate limiting
    if "429" in err_str or "resource_exhausted" in err_str or "rate limit" in err_str or "quota" in err_str:
        return ProviderError(
            ErrorCategory.RATE_LIMIT,
            f"Provider rate limit exceeded: {exc}",
            retryable=True,
            status_code=429,
            cause=exc,
        )

    # Bad Request / 400
    if "400" in err_str or "bad request" in err_str or "invalid argument" in err_str or "invalid_argument" in err_str:
        return ProviderError(
            ErrorCategory.SCHEMA_ERROR,
            f"Provider rejected request as invalid: {exc}",
            retryable=False,
            status_code=400,
            cause=exc,
        )

    # Authentication
    if "401" in err_str or "403" in err_str or "unauthenticated" in err_str or "permission_denied" in err_str or "api key" in err_str:
        return ProviderError(
            ErrorCategory.AUTH_ERROR,
            f"Provider authentication failed: {exc}",
            retryable=False,
            status_code=401 if "401" in err_str else 403,
            cause=exc,
        )

    # Timeouts
    if isinstance(exc, TimeoutError) or "timeout" in err_str or "deadline_exceeded" in err_str or "504" in err_str:
        return ProviderError(
            ErrorCategory.TIMEOUT,
            f"Provider request timed out: {exc}",
            retryable=True,
            status_code=504,
            cause=exc,
        )

    # Network
    if isinstance(exc, (ConnectionError, OSError)) or "connection" in err_str or "socket" in err_str or "network" in err_str:
        return ProviderError(
            ErrorCategory.NETWORK_ERROR,
            f"Network connectivity error: {exc}",
            retryable=True,
            cause=exc,
        )

    # Safety blocks
    if "safety" in err_str or "blocked" in err_str or "content filter" in err_str:
        return ProviderError(
            ErrorCategory.SAFETY_BLOCK,
            f"Provider blocked content due to safety filters: {exc}",
            retryable=False,
            cause=exc,
        )

    # Server errors (5xx)
    if "500" in err_str or "502" in err_str or "503" in err_str or "internal" in err_str or "unavailable" in err_str:
        return ProviderError(
            ErrorCategory.SERVER_ERROR,
            f"Provider server-side error: {exc}",
            retryable=True,
            status_code=500,
            cause=exc,
        )

    # Invalid response / JSON parsing
    if "jsondecodeerror" in exc_type or "json" in err_str or "not a json" in err_str:
        return ProviderError(
            ErrorCategory.INVALID_RESPONSE,
            f"Provider returned unparseable response: {exc}",
            retryable=False,
            cause=exc,
        )

    # Schema errors
    if "validationerror" in exc_type or "schema" in err_str or "valueerror" in exc_type:
        return ProviderError(
            ErrorCategory.SCHEMA_ERROR,
            f"Provider response violated output schema: {exc}",
            retryable=False,
            cause=exc,
        )

    return ProviderError(
        ErrorCategory.UNKNOWN,
        f"Unexpected provider error: {exc}",
        retryable=False,
        cause=exc,
    )
