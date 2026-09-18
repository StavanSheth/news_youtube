"""Deterministic scoring, specificity calculation, and confidence evaluation."""

from __future__ import annotations

from typing import Any
from ..classification import KeywordClassifier


def score_micro_topic_chunk(chunk_text: str, classification: dict[str, Any]) -> dict[str, Any]:
    """Score one chunk using the authoritative classification signals."""
    positive = list(classification.get("positive_signals", classification.get("signals", [])))
    negative = list(classification.get("matched_negative_signals", classification.get("negative_signals", [])))
    result = KeywordClassifier.score(
        chunk_text,
        positive,
        negative,
        signal_groups=classification.get("signal_groups", {}),
        disambiguators=classification.get("disambiguators", []),
    )
    return {
        **result,
        "relevant": bool(result["matched_signals"] and not result.get("hard_rejection_reason") and result["score"] > 0),
    }


def compute_confidence(
    classification_score: float,
    margin: float,
    signals: list[str] | tuple[str, ...],
    contradiction_penalty: float = 0.0,
) -> float:
    """Calculate deterministic confidence based on score, margin, specificity, and contradictions."""
    specificity = min(1.0, sum(max(1, len(str(signal).split())) for signal in signals) / 12)
    confidence = round(
        max(
            0.0,
            min(
                1.0,
                0.45 * classification_score
                + 0.25 * min(1.0, margin / 0.3)
                + 0.2 * specificity
                + 0.1 * (1.0 - contradiction_penalty),
            ),
        ),
        3,
    )
    return confidence
