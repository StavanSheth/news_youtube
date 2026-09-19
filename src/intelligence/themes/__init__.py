"""Theme intelligence engine package."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .contracts import ThemeContract, ThemeResolution, validate_theme_contract
from .inheritance import ThemeTemplateRegistry
from .quality import (
    generate_theme_health_json,
    is_generic_theme,
    theme_difference_score,
    theme_fingerprint,
    theme_lexical_overlap,
    theme_quality_score,
    theme_semantic_overlap,
    theme_specificity_score,
    validate_theme_completeness,
)
from .resolver import analysis_profile
from .routing import select_theme
from .snapshots import (
    compute_theme_fingerprint,
    create_theme_snapshot,
    verify_theme_snapshot,
)

if TYPE_CHECKING:
    from .coverage import ThemeCoverageValidator

__all__ = [
    "ThemeContract",
    "ThemeCoverageValidator",
    "ThemeResolution",
    "ThemeTemplateRegistry",
    "analysis_profile",
    "compute_theme_fingerprint",
    "create_theme_snapshot",
    "generate_theme_health_json",
    "is_generic_theme",
    "select_theme",
    "theme_difference_score",
    "theme_fingerprint",
    "theme_lexical_overlap",
    "theme_quality_score",
    "theme_semantic_overlap",
    "theme_specificity_score",
    "validate_theme_completeness",
    "validate_theme_contract",
    "verify_theme_snapshot",
]


def __getattr__(name: str) -> Any:
    if name == "ThemeCoverageValidator":
        from .coverage import ThemeCoverageValidator
        return ThemeCoverageValidator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
