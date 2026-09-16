from __future__ import annotations

from datetime import UTC, datetime
from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True)
class SignalMatch:
    signal_id: str
    phrase: str
    start: int
    end: int
    signal_type: str
    strength: str
    source_field: str

    def to_dict(self) -> dict[str, Any]:
        return {"signal_id": self.signal_id, "phrase": self.phrase, "start": self.start, "end": self.end, "signal_type": self.signal_type, "strength": self.strength, "source_field": self.source_field}


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
    def matching_spans(cls, phrases: list[str] | list[dict[str, Any]], text: str, *, source_field: str) -> list[SignalMatch]:
        haystack = cls.normalize(text)
        matches: list[SignalMatch] = []
        for raw in phrases:
            phrase = str(raw.get("phrase", "") if isinstance(raw, dict) else raw)
            normalized = cls.normalize(phrase)
            if not normalized:
                continue
            found = re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", haystack)
            if found and not re.search(r"\b(?:no|not|without|never)\b", haystack[max(0, found.start() - 24):found.start()]):
                strength = str(raw.get("strength", "medium") if isinstance(raw, dict) else "medium").lower()
                signal_type = str(raw.get("type", "positive") if isinstance(raw, dict) else "positive").lower()
                signal_id = str(raw.get("signal_id", f"signal-{re.sub(r'[^a-z0-9]+', '-', normalized).strip('-')}") if isinstance(raw, dict) else f"signal-{re.sub(r'[^a-z0-9]+', '-', normalized).strip('-')}")
                matches.append(SignalMatch(signal_id, phrase, found.start(), found.end(), signal_type, strength, source_field))
        return matches

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
        distractors: list[str] = []
        exclusions: list[str] = []
        contributions: dict[str, float] = {"distractor": 0.0, "contradiction": 0.0, "exclusion": 0.0}
        hard_rejection_reason = None
        normalized_text = cls.normalize(text)
        for phrase in matched:
            entry = entries.get(cls.normalize(phrase), phrase)
            strength = str(entry.get("strength", "medium") if isinstance(entry, dict) else "medium").lower()
            signal_type = str(entry.get("type", "contradiction" if strength == "strong" else "distractor") if isinstance(entry, dict) else "distractor").lower()
            value = penalties.get(strength, penalties["medium"])
            index = normalized_text.find(cls.normalize(phrase))
            nearby_positive = any(abs(index - normalized_text.find(cls.normalize(pos))) <= 90 for pos in positive_matches if normalized_text.find(cls.normalize(pos)) >= 0)
            if signal_type == "distractor" and nearby_positive and phrase not in title_matches:
                value *= 0.35
            if signal_type == "contradiction" and phrase in title_matches and not nearby_positive:
                contradictions.append(phrase) if strength == "strong" else None
            if signal_type == "exclusion":
                value *= 1.25
                exclusions.append(phrase)
                hard_rejection_reason = f"hard_exclusion:{phrase}"
            elif signal_type == "distractor":
                distractors.append(phrase)
            elif signal_type == "contradiction":
                contradictions.append(phrase) if phrase not in contradictions else None
            effective.append(phrase)
            contribution = value * (1.5 if phrase in title_matches else 1.0)
            contributions[signal_type] = round(contributions.get(signal_type, 0.0) + contribution, 3)
            penalty += contribution
        contradiction_penalty = min(0.35, len(contradictions) * 0.25)
        return {
            "matched_negative_signals": effective,
            "negative_penalty": round(min(0.8, penalty), 3),
            "contradiction_penalty": round(contradiction_penalty, 3),
            "negative_strengths": {phrase: str(entries.get(cls.normalize(phrase), {}).get("strength", "medium") if isinstance(entries.get(cls.normalize(phrase)), dict) else "medium") for phrase in effective},
            "matched_distractors": distractors,
            "matched_contradictions": contradictions,
            "matched_exclusions": exclusions,
            "negative_contributions": contributions,
            "hard_rejection_reason": hard_rejection_reason,
        }

    @classmethod
    def score(
        cls,
        text: str,
        positive: list[str] | list[dict[str, Any]],
        negative: list[str] | list[dict[str, Any]],
        *,
        title: str = "",
        signal_groups: dict[str, list[str] | list[dict[str, Any]]] | None = None,
        disambiguators: list[str] | None = None,
    ) -> dict[str, Any]:
        matched = cls.matching(positive, text)
        positive_spans = cls.matching_spans(positive, text, source_field="positive")
        negative_spans = cls.matching_spans(negative, text, source_field="negative")
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
        matched_groups = {
            name: cls.matching(values, text)
            for name, values in (signal_groups or {}).items()
            if cls.matching(values, text)
        }
        disambiguator_matches = cls.matching(disambiguators or [], text)
        group_bonus = min(0.2, len(matched_groups) * 0.06)
        disambiguator_bonus = min(0.12, len(disambiguator_matches) * 0.04)
        score = min(1.0, max(0.0, positive_score + group_bonus + disambiguator_bonus - negative_result["negative_penalty"] - negative_result["contradiction_penalty"]))
        if negative_result["hard_rejection_reason"]:
            score = 0.0
        return {
            "matched_signals": matched,
            "signal_matches": [match.to_dict() for match in [*positive_spans, *negative_spans]],
            "negative_signals": negative_result["matched_negative_signals"],
            "title_matches": title_matches,
            "body_matches": body_matches,
            "positive_score": round(positive_score, 3),
            "matched_signal_groups": matched_groups,
            "disambiguator_matches": disambiguator_matches,
            "negative_penalty": negative_result["negative_penalty"],
            "contradiction_penalty": negative_result["contradiction_penalty"],
            "negative_strengths": negative_result["negative_strengths"],
            "matched_distractors": negative_result["matched_distractors"],
            "matched_contradictions": negative_result["matched_contradictions"],
            "matched_exclusions": negative_result["matched_exclusions"],
            "signal_contributions": {"positive": round(positive_score, 3), "groups": round(group_bonus, 3), "disambiguation": round(disambiguator_bonus, 3), **negative_result["negative_contributions"]},
            "hard_rejection_reason": negative_result["hard_rejection_reason"],
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


def select_micro_topic_decisions(
    candidates: list[dict[str, Any]],
    *,
    default_primary_threshold: float = 0.5,
    default_secondary_threshold: float = 0.5,
    default_runner_up_margin: float = 0.05,
    default_max_secondary: int = 1,
) -> list[dict[str, Any]]:
    """Deterministic selection of primary, secondary, ambiguous, or rejected decisions without side-effects."""
    if not candidates:
        return []

    # Copy and sort descending by score, then micro_topic_id for tie-breaking
    sorted_candidates = [dict(c) for c in candidates]
    sorted_candidates.sort(
        key=lambda c: (-float(c.get("classification_score", c.get("score", 0.0))), str(c.get("micro_topic_id", c.get("micro_topic", "")))),
    )

    primary = sorted_candidates[0]
    primary_score = float(primary.get("classification_score", primary.get("score", 0.0)))
    runner_up_score = float(sorted_candidates[1].get("classification_score", sorted_candidates[1].get("score", 0.0))) if len(sorted_candidates) > 1 else 0.0
    margin = round(primary_score - runner_up_score, 3)

    primary_threshold = float(primary.get("primary_threshold", primary.get("classification_threshold", default_primary_threshold)))
    runner_up_margin = float(primary.get("runner_up_margin", default_runner_up_margin))

    if primary.get("hard_rejection_reason"):
        return []

    if primary_score < primary_threshold:
        return []

    selected: list[dict[str, Any]] = []
    secondary_count = 0

    for index, candidate in enumerate(sorted_candidates):
        cand = dict(candidate)
        cand_score = float(cand.get("classification_score", cand.get("score", 0.0)))
        cand_sec_thresh = float(cand.get("secondary_threshold", cand.get("classification_threshold", default_secondary_threshold)))

        if index == 0:
            if margin < runner_up_margin and not cand.get("disambiguators") and not cand.get("matched_signal_groups"):
                status = "AMBIGUOUS"
            else:
                status = "PRIMARY"
        elif cand_score < cand_sec_thresh:
            continue
        elif secondary_count >= int(primary.get("max_secondary", default_max_secondary)):
            continue
        else:
            status = "SECONDARY"
            secondary_count += 1

        cand["decision"] = status
        cand["margin"] = margin
        cand["primary_score"] = primary_score
        cand["runner_up_score"] = runner_up_score
        selected.append(cand)

    return selected


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
