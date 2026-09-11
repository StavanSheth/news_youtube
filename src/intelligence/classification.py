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
    def matching(cls, phrases: list[str] | list[dict[str, Any]], text: str) -> list[str]:
        haystack = cls.normalize(text)
        matched = set()
        for raw in phrases:
            phrase = raw.get("phrase", "") if isinstance(raw, dict) else raw
            normalized = cls.normalize(phrase)
            if not normalized:
                continue
            for found in re.finditer(rf"(?<!\w){re.escape(normalized)}(?!\w)", haystack):
                prefix = haystack[max(0, found.start() - 24):found.start()]
                if re.search(r"\b(?:no|not|without|never)\b", prefix):
                    continue
                matched.add(str(phrase))
                break
        return sorted(matched)

    @classmethod
    def negative_signal_score(
        cls,
        text: str,
        negative: list[str] | list[dict[str, Any]],
        *,
        title: str = "",
        positive_matches: list[str] | None = None,
    ) -> dict[str, Any]:
        """Score exclusions without treating incidental context as contradiction."""
        positive_matches = positive_matches or []
        title_matches = set(cls.matching(negative, title))
        matched = cls.matching(negative, text)
        entries = {cls.normalize(str(item.get("phrase", "")) if isinstance(item, dict) else str(item)): item for item in negative}
        penalties = {"weak": 0.07, "medium": 0.16, "strong": 0.28}
        penalty = 0.0
        effective: list[str] = []
        contradictions: list[str] = []
        normalized_text = cls.normalize(text)
        for phrase in matched:
            entry = entries.get(cls.normalize(phrase), phrase)
            strength = str(entry.get("strength", "medium") if isinstance(entry, dict) else "medium").lower()
            value = penalties.get(strength, penalties["medium"])
            index = normalized_text.find(cls.normalize(phrase))
            nearby_positive = any(abs(index - normalized_text.find(cls.normalize(pos))) <= 90 for pos in positive_matches if normalized_text.find(cls.normalize(pos)) >= 0)
            if nearby_positive and phrase not in title_matches:
                value *= 0.35
            if phrase in title_matches and not nearby_positive:
                contradictions.append(phrase) if strength == "strong" else None
            effective.append(phrase)
            penalty += value * (1.5 if phrase in title_matches else 1.0)
        contradiction_penalty = min(0.35, len(contradictions) * 0.25)
        return {
            "matched_negative_signals": effective,
            "negative_penalty": round(min(0.8, penalty), 3),
            "contradiction_penalty": round(contradiction_penalty, 3),
            "negative_strengths": {phrase: str(entries.get(cls.normalize(phrase), {}).get("strength", "medium") if isinstance(entries.get(cls.normalize(phrase)), dict) else "medium") for phrase in effective},
        }

    @classmethod
    def score(cls, text: str, positive: list[str] | list[dict[str, Any]], negative: list[str] | list[dict[str, Any]], *, title: str = "") -> dict[str, Any]:
        matched = cls.matching(positive, text)
        title_matches = cls.matching(positive, title)
        body_matches = [value for value in matched if value not in title_matches]
        entries = {cls.normalize(str(item.get("phrase", "")) if isinstance(item, dict) else str(item)): item for item in positive}
        strengths = {"weak": 0.10, "medium": 0.18, "strong": 0.36}
        positive_score = 0.0
        for phrase in matched:
            entry = entries.get(cls.normalize(phrase), phrase)
            strength = str(entry.get("strength", "medium") if isinstance(entry, dict) else "medium").lower()
            positive_score += strengths.get(strength, strengths["medium"])
            if phrase in title_matches:
                positive_score += 0.14
        negative_result = cls.negative_signal_score(text, negative, title=title, positive_matches=matched)
        score = min(1.0, max(0.0, positive_score - negative_result["negative_penalty"] - negative_result["contradiction_penalty"]))
        return {
            "matched_signals": matched,
            "negative_signals": negative_result["matched_negative_signals"],
            "title_matches": title_matches,
            "body_matches": body_matches,
            "positive_score": round(positive_score, 3),
            "negative_penalty": negative_result["negative_penalty"],
            "contradiction_penalty": negative_result["contradiction_penalty"],
            "negative_strengths": negative_result["negative_strengths"],
            "score": round(score, 3),
        }


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
