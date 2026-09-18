"""Authoritative AI provider package for Gemini, DryRun, and structured analysis."""

from __future__ import annotations

from .base import AIProvider, AIRequest, AIResponse
from .dry_run import DryRunProvider, FakeAIProvider
from .errors import ErrorCategory, ProviderError, RETRYABLE_CATEGORIES, classify_gemini_error
from .gemini import (
    GeminiProvider,
    SOURCE_DATA_POLICY,
    UNTRUSTED_CONTENT_FOOTER,
    UNTRUSTED_CONTENT_HEADER,
    _json_object,
)
from .retry import with_retry
from .schemas import (
    ActionableInsight,
    AnalysisOutput,
    EvidenceItem,
    EvidenceTypeEnum,
    FactClaim,
    InterpretationClaim,
)
from .usage import TokenUsage, calculate_cost, estimate_tokens

__all__ = [
    "AIProvider",
    "AIRequest",
    "AIResponse",
    "ActionableInsight",
    "AnalysisOutput",
    "DryRunProvider",
    "ErrorCategory",
    "EvidenceItem",
    "EvidenceTypeEnum",
    "FactClaim",
    "FakeAIProvider",
    "GeminiProvider",
    "InterpretationClaim",
    "ProviderError",
    "RETRYABLE_CATEGORIES",
    "SOURCE_DATA_POLICY",
    "TokenUsage",
    "UNTRUSTED_CONTENT_FOOTER",
    "UNTRUSTED_CONTENT_HEADER",
    "_json_object",
    "calculate_cost",
    "classify_gemini_error",
    "estimate_tokens",
    "with_retry",
]
