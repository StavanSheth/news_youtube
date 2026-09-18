"""Theme intelligence engine package."""

from __future__ import annotations

from .contracts import ThemeContract, ThemeResolution
from .quality import (
    is_generic_theme,
    theme_difference_score,
    theme_fingerprint,
    theme_lexical_overlap,
    theme_quality_score,
    theme_semantic_overlap,
    theme_specificity_score,
)
from .resolver import analysis_profile
from .routing import select_theme

__all__ = [
    "ThemeContract",
    "ThemeResolution",
    "analysis_profile",
    "is_generic_theme",
    "select_theme",
    "theme_difference_score",
    "theme_fingerprint",
    "theme_lexical_overlap",
    "theme_quality_score",
    "theme_semantic_overlap",
    "theme_specificity_score",
]
