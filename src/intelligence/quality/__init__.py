"""Quality, scoring, and output validation framework."""

from __future__ import annotations

from .output import _HTMLBalance, _valid_url, evaluate_output
from .score import CategoryResult, CheckItem, compute_category_score

__all__ = [
    "_HTMLBalance",
    "_valid_url",
    "evaluate_output",
    "CheckItem",
    "CategoryResult",
    "compute_category_score",
]
