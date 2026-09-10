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
