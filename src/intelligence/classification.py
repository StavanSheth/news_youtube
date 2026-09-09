from __future__ import annotations

from datetime import UTC, datetime


def classify(text: str, topics: list[dict]) -> list[dict]:
    haystack = text.lower()
    matches = []
    for topic in topics:
        found = [word for word in topic.get("keywords", []) if word.lower() in haystack]
        if found:
            matches.append(
                {
                    "topic": topic,
                    "matches": found,
                    "coverage": len(found) / max(len(topic.get("keywords", [])), 1),
                }
            )
    return matches


def relevance_score(item, matches: list[dict], scoring: dict) -> float:
    if not matches:
        return 0.0
    topic = max(entry["coverage"] for entry in matches)
    keyword = min(len({word for entry in matches for word in entry["matches"]}) / 5, 1.0)
    priority = min(float(item.priority), 2.0) / 2.0
    recency = 1.0
    if item.published_at:
        try:
            age = (datetime.now(UTC) - datetime.fromisoformat(item.published_at)).days
            recency = max(0.0, 1 - age / 14)
        except ValueError:
            pass
    return round(
        topic * scoring.get("topic_match_weight", 0.45)
        + keyword * scoring.get("keyword_match_weight", 0.20)
        + priority * scoring.get("source_priority_weight", 0.20)
        + recency * scoring.get("recency_weight", 0.15),
        3,
    )
