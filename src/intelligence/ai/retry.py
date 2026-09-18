"""Bounded exponential backoff and retry policy for AI provider calls."""

from __future__ import annotations

import logging
import random
import time
from typing import Callable, TypeVar

from .errors import RETRYABLE_CATEGORIES, ErrorCategory, ProviderError, classify_gemini_error

logger = logging.getLogger(__name__)

T = TypeVar("T")


def with_retry(
    fn: Callable[[], T],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 5.0,
    jitter: bool = True,
    retryable_categories: set[ErrorCategory] | None = None,
    on_retry: Callable[[int, ProviderError, float], None] | None = None,
) -> T:
    """Execute a callable with bounded exponential backoff on retryable errors.

    Args:
        fn: Zero-argument callable to execute.
        max_attempts: Maximum number of invocation attempts.
        base_delay: Initial sleep duration in seconds.
        max_delay: Maximum sleep duration cap in seconds.
        jitter: Whether to apply randomized multiplicative jitter.
        retryable_categories: Set of error categories eligible for retry.
        on_retry: Optional callback invoked before sleeping on retryable error.

    Returns:
        Result of the successful invocation.

    Raises:
        ProviderError: When all attempts fail or non-retryable error occurs.
    """
    allowed_categories = retryable_categories if retryable_categories is not None else RETRYABLE_CATEGORIES
    last_error: ProviderError | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:
            prov_error = classify_gemini_error(exc)
            last_error = prov_error

            if attempt >= max_attempts or prov_error.category not in allowed_categories or not prov_error.retryable:
                logger.warning(
                    "AI provider call failed on attempt %d/%d (category=%s, retryable=%s): %s",
                    attempt,
                    max_attempts,
                    prov_error.category.value,
                    prov_error.retryable,
                    prov_error.message,
                )
                raise prov_error from exc

            # Calculate exponential backoff with full jitter
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            if jitter:
                delay = delay * (0.75 + 0.5 * random.random())

            logger.info(
                "Retrying AI provider call after attempt %d/%d in %.2fs due to %s: %s",
                attempt,
                max_attempts,
                delay,
                prov_error.category.value,
                prov_error.message,
            )

            if on_retry is not None:
                on_retry(attempt, prov_error, delay)

            time.sleep(delay)

    assert last_error is not None
    raise last_error
