"""Small deterministic benchmark for Phase 2 routing regressions."""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable


def evaluate_golden(records: list[dict[str, Any]], classify: Callable[[dict[str, Any]], list[dict[str, Any]]]) -> dict[str, Any]:
    expected = []
    predicted = []
    for record in records:
        matches = classify(record)
        labels = [match["micro_topic"] for match in matches]
        expected.append(record.get("primary_micro_topic"))
        predicted.append(labels[0] if labels else None)
    tp = sum(actual == guess and actual is not None for actual, guess in zip(expected, predicted))
    fp = sum(guess is not None and guess != actual for actual, guess in zip(expected, predicted))
    fn = sum(actual is not None and actual != guess for actual, guess in zip(expected, predicted))
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-9, precision + recall)
    confusion = Counter((actual, guess) for actual, guess in zip(expected, predicted) if actual != guess)
    return {
        "records": len(records), "true_positive": tp, "false_positive": fp, "false_negative": fn,
        "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
        "false_positive_rate": round(fp / max(1, len(records)), 3),
        "false_negative_rate": round(fn / max(1, len(records)), 3),
        "confusion_pairs": [{"expected": pair[0], "predicted": pair[1], "count": count} for pair, count in confusion.most_common()],
    }
