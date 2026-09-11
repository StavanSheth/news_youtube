"""Small deterministic benchmark for Phase 2 routing regressions."""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable


def evaluate_golden(records: list[dict[str, Any]], classify: Callable[[dict[str, Any]], list[dict[str, Any]]]) -> dict[str, Any]:
    expected_primary: list[str | None] = []
    expected_sets: list[set[str]] = []
    predicted_primary: list[str | None] = []
    predicted_sets: list[set[str]] = []
    for record in records:
        matches = classify(record)
        labels = [match["micro_topic"] for match in matches]
        actual = {record["primary_micro_topic"], *record.get("secondary_micro_topics", [])}
        expected_primary.append(record.get("primary_micro_topic"))
        expected_sets.append(actual)
        predicted_primary.append(labels[0] if labels else None)
        predicted_sets.append(set(labels))
    labels = sorted(set().union(*expected_sets, *predicted_sets)) if records else []
    tp = sum(len(actual & guess) for actual, guess in zip(expected_sets, predicted_sets))
    fp = sum(len(guess - actual) for actual, guess in zip(expected_sets, predicted_sets))
    fn = sum(len(actual - guess) for actual, guess in zip(expected_sets, predicted_sets))
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-9, precision + recall)
    per_topic = {}
    for label in labels:
        label_tp = sum(label in actual and label in guess for actual, guess in zip(expected_sets, predicted_sets))
        label_fp = sum(label not in actual and label in guess for actual, guess in zip(expected_sets, predicted_sets))
        label_fn = sum(label in actual and label not in guess for actual, guess in zip(expected_sets, predicted_sets))
        p = label_tp / max(1, label_tp + label_fp)
        r = label_tp / max(1, label_tp + label_fn)
        per_topic[label] = {"support": sum(label in actual for actual in expected_sets), "predictions": sum(label in guess for guess in predicted_sets), "precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / max(1e-9, p + r), 3)}
    macro_f1 = sum(item["f1"] for item in per_topic.values()) / max(1, len(per_topic))
    weighted_f1 = sum(item["f1"] * item["support"] for item in per_topic.values()) / max(1, sum(item["support"] for item in per_topic.values()))
    secondary_expected = [actual - {primary} for actual, primary in zip(expected_sets, expected_primary)]
    secondary_predicted = [guess - {primary} for guess, primary in zip(predicted_sets, predicted_primary)]
    secondary_tp = sum(len(a & p) for a, p in zip(secondary_expected, secondary_predicted))
    secondary_fp = sum(len(p - a) for a, p in zip(secondary_expected, secondary_predicted))
    secondary_fn = sum(len(a - p) for a, p in zip(secondary_expected, secondary_predicted))
    secondary_precision = secondary_tp / max(1, secondary_tp + secondary_fp)
    secondary_recall = secondary_tp / max(1, secondary_tp + secondary_fn)
    confusion = Counter((actual, guess) for actual, guess in zip(expected_primary, predicted_primary) if actual != guess)
    return {
        "records": len(records), "primary_accuracy": round(sum(a == p for a, p in zip(expected_primary, predicted_primary)) / max(1, len(records)), 3),
        "true_positive": tp, "false_positive": fp, "false_negative": fn,
        "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
        "micro_precision": round(precision, 3), "micro_recall": round(recall, 3), "micro_f1": round(f1, 3),
        "macro_f1": round(macro_f1, 3), "weighted_f1": round(weighted_f1, 3),
        "exact_set_accuracy": round(sum(a == p for a, p in zip(expected_sets, predicted_sets)) / max(1, len(records)), 3),
        "secondary_precision": round(secondary_precision, 3), "secondary_recall": round(secondary_recall, 3),
        "false_positive_rate": round(fp / max(1, len(records)), 3), "false_negative_rate": round(fn / max(1, len(records)), 3),
        "zero_prediction_micro_topics": [label for label, item in per_topic.items() if item["predictions"] == 0],
        "worst_performing_micro_topics": sorted(per_topic, key=lambda label: (per_topic[label]["f1"], label))[:5],
        "per_micro_topic": per_topic,
        "confusion_pairs": [{"expected": pair[0], "predicted": pair[1], "count": count} for pair, count in confusion.most_common()],
    }
