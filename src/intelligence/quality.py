"""Deterministic output checks. These checks never invent a quality score."""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse


class _HTMLBalance(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.open_tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in {"meta", "link", "img", "br", "hr", "input"}:
            self.open_tags.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.open_tags and self.open_tags[-1] == tag:
            self.open_tags.pop()


def _valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def evaluate_output(
    stories: list[dict[str, Any]],
    markdown: str,
    html: str,
    coverage: list[dict[str, Any]],
    source_health: dict[str, Any],
) -> dict[str, Any]:
    checks: dict[str, bool] = {
        "no_duplicate_stories": len({
            (
                story.get("id"),
                tuple(sorted((entry.get("domain", ""), entry.get("micro_topic", "")) for entry in story.get("micro_topics", []))),
            )
            for story in stories
        }) == len(stories),
        "no_duplicate_facts": all(
            len(facts) == len(set(facts))
            for facts in (story.get("analysis", {}).get("facts", []) for story in stories)
        ),
        "source_links": all(_valid_url(story.get("url", "")) for story in stories),
        "source_labels": all(bool(story.get("source")) for story in stories),
        "importance_present": all(0 <= float(story.get("importance_score", -1)) <= 100 for story in stories),
        "confidence_present": all(0 <= float(story.get("confidence_score", -1)) <= 100 for story in stories),
        "micro_topic_present": all(bool(story.get("micro_topics")) for story in stories),
        "theme_present": all(bool(story.get("theme")) for story in stories),
        "evidence_classified": all(
            all(entry.get("type") in {"fact", "official_statement", "reported_claim", "opinion", "inference", "speculation"} for entry in story.get("analysis", {}).get("evidence", []))
            for story in stories
        ),
        "claims_cited": all(
            not story.get("analysis", {}).get("facts")
            or (
                bool([entry for entry in story.get("analysis", {}).get("evidence", []) if entry.get("type") in {"fact", "official_statement", "reported_claim"}])
                and all(
                    _valid_url(entry.get("source_url", ""))
                    for entry in story.get("analysis", {}).get("evidence", [])
                    if entry.get("type") in {"fact", "official_statement", "reported_claim"}
                )
            )
            for story in stories
        ),
        "coverage_present": bool(coverage),
        "markdown_present": bool(markdown.strip()),
        "html_present": bool(html.strip()),
    }
    parser = _HTMLBalance()
    try:
        parser.feed(html)
        checks["html_balanced"] = not parser.open_tags
    except Exception:
        checks["html_balanced"] = False
    checks["source_health_recorded"] = bool(source_health)
    checks["source_health_ok"] = bool(source_health) and all(
        value.get("status") in {"HEALTHY", "EMPTY"} for value in source_health.values()
    )
    buckets = {
        "coverage_score": ["coverage_present", "source_health_recorded", "source_health_ok"],
        "classification_score": ["micro_topic_present"],
        "theme_score": ["theme_present"],
        "evidence_score": ["no_duplicate_facts", "source_links", "evidence_classified", "claims_cited"],
        "newsletter_score": ["markdown_present", "html_present", "html_balanced"],
    }
    scores = {
        name: round(sum(checks.get(check, False) for check in required) / len(required) * 100)
        for name, required in buckets.items()
    }
    scores["retrieval_score"] = round(sum(bool(story.get("retrieved_evidence")) for story in stories) / max(1, len(stories)) * 100)
    scores["source_score"] = round(sum(value.get("status") in {"HEALTHY", "EMPTY"} for value in source_health.values()) / max(1, len(source_health)) * 100)
    scores["actionability_score"] = round(sum(bool(story.get("analysis", {}).get("actionable_insights")) for story in stories) / max(1, len(stories)) * 100)
    scores["intelligence_score"] = round(sum(scores[name] for name in ("classification_score", "theme_score", "evidence_score", "actionability_score")) / 4)
    scores["overall"] = round(sum(scores.values()) / len(scores))
    return {
        "checks": checks,
        "scores": scores,
        "passed": all(checks.values()) and scores["overall"] >= 95,
        "minimum_score": 95,
    }
