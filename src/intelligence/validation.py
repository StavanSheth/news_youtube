from __future__ import annotations

from typing import Any


def validate_taxonomy(taxonomy: dict[str, Any]) -> None:
    required = {"domains", "priorities", "event_types", "report_types"}
    missing = required - taxonomy.keys()
    if missing:
        raise ValueError(f"Taxonomy missing required fields: {sorted(missing)}")
    for field in required:
        values = taxonomy[field]
        if not isinstance(values, list) or not values or not all(isinstance(value, str) and value for value in values):
            raise ValueError(f"Taxonomy field {field!r} must be a non-empty list of strings")
        if len(values) != len(set(values)):
            raise ValueError(f"Taxonomy field {field!r} contains duplicates")


def validate_topics(topics: list[dict[str, Any]], taxonomy: dict[str, Any]) -> None:
    keys = [topic.get("key", topic.get("id")) for topic in topics]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise ValueError("Topics must have unique non-empty keys")
    for topic in topics:
        threshold = float(topic.get("classification_threshold", 0.25))
        if not 0 <= threshold <= 1:
            raise ValueError(f"Invalid classification threshold for {topic.get('name')}")
        report_type = topic.get("report_type")
        if report_type and report_type not in taxonomy["report_types"]:
            raise ValueError(f"Invalid report type: {report_type}")
