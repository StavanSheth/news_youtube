from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any


class KeywordClassifier:
    """Domain-agnostic deterministic signal matcher and scorer."""

    @staticmethod
    def normalize(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "").lower()).strip()

    @classmethod
    def matching(cls, phrases: list[str], text: str) -> list[str]:
        haystack = cls.normalize(text)
        return sorted({phrase for phrase in phrases if phrase and re.search(rf"(?<!\w){re.escape(cls.normalize(phrase))}(?!\w)", haystack)})

    @classmethod
    def score(cls, text: str, positive: list[str], negative: list[str], *, title: str = "") -> dict[str, Any]:
        matched = cls.matching(positive, text)
        rejected = cls.matching(negative, text)
        title_matches = cls.matching(positive, title)
        body_matches = [value for value in matched if value not in title_matches]
        score = min(1.0, max(0.0, len(title_matches) * 0.2 + len(body_matches) * 0.15 + len(matched) * 0.35 - len(cls.matching(negative, title)) * 0.35 - len(rejected) * 0.15))
        return {"matched_signals": matched, "negative_signals": rejected, "title_matches": title_matches, "body_matches": body_matches, "score": round(score, 3)}


def topic_matches(item: dict[str, Any], topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compatibility topic-level classifier owned by the shared classification module."""
    text = f"{item.get('title', '')}\n{item.get('text', '')}"
    matches = []
    for raw in topics:
        if not raw.get("enabled", True):
            continue
        terms = [str(term) for term in raw.get("keywords", []) + raw.get("aliases", [])]
        found = KeywordClassifier.matching(terms, text)
        score = len(found) / max(1, min(4, len(terms)))
        if score >= float(raw.get("classification_threshold", 0.25)):
            matches.append({"key": raw.get("key", raw.get("id", raw["name"].lower().replace(" ", "-"))), "name": raw["name"], "score": round(score, 2), "config": raw, "matches": found})
    return sorted(matches, key=lambda match: (match["score"], match["config"].get("priority", 0)), reverse=True)


def relevance(item: dict[str, Any], topics: list[dict[str, Any]], weights: dict[str, float]) -> float:
    if not topics:
        return 0.0
    published = _parse_time(item.get("published_at", ""))
    age_hours = max(0.0, (datetime.now(UTC) - published).total_seconds() / 3600) if published else 72.0
    recency = max(0.0, 1 - age_hours / 168)
    completeness = min(len(item.get("text", "")) / 1500, 1.0)
    topic_score = max(topic["score"] for topic in topics)
    priority = min(float(item.get("priority", 1)) / 10, 1.0)
    return round(topic_score * weights.get("topic_relevance", 0.4) + priority * weights.get("source_priority", 0.2) + recency * weights.get("recency", 0.2) + completeness * weights.get("content_completeness", 0.2), 3)


def _parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


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
