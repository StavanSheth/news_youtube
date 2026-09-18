"""Authoritative backward-compatible facade delegating directly to intelligence.ai."""

from __future__ import annotations

from .ai import (
    SOURCE_DATA_POLICY,
    AIProvider,
    DryRunProvider,
    FakeAIProvider,
    GeminiProvider,
    _json_object,
)

__all__ = [
    "AIProvider",
    "DryRunProvider",
    "FakeAIProvider",
    "GeminiProvider",
    "SOURCE_DATA_POLICY",
    "_json_object",
]
