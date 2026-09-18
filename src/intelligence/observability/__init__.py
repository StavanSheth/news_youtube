"""Authoritative observability package providing structured logging, metrics, and health checks."""

from __future__ import annotations

from .health import check_system_health
from .logging import StructuredJsonFormatter, mask_secrets, setup_structured_logging
from .metrics import MetricsRegistry, default_metrics

__all__ = [
    "MetricsRegistry",
    "StructuredJsonFormatter",
    "check_system_health",
    "default_metrics",
    "mask_secrets",
    "setup_structured_logging",
]
