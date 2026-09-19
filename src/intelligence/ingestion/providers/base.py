"""Authoritative SourceProvider protocol for provider-specific validation and collection."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ...sources import CollectionBudget, SourceAcceptanceResult, SourceContract
from ..base import CanonicalContent


@runtime_checkable
class SourceProvider(Protocol):
    """Authoritative protocol for provider-specific validation, collection, and health."""

    def validate(
        self,
        source: SourceContract,
        run_id: str = "validation",
        live: bool = False,
    ) -> SourceAcceptanceResult:
        """Execute provider-specific validation and return acceptance result."""
        ...

    def collect(
        self,
        source: SourceContract,
        budget: CollectionBudget | None = None,
        live: bool = False,
    ) -> list[CanonicalContent]:
        """Collect content and normalize to CanonicalContent adhering to budget limits."""
        ...

    def health(
        self,
        source: SourceContract,
    ) -> dict[str, Any]:
        """Return provider-specific health metrics and state."""
        ...
