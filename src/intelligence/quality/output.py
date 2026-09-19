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
    """Evaluate story outputs against strict quality gates and invariant bounds."""
    # 1. Base deterministic quality checks
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
            all(
                entry.get("type") in {
                    "fact", "official_statement", "reported_claim", "opinion", "inference", "speculation"
                }
                for entry in story.get("analysis", {}).get("evidence", [])
            )
            for story in stories
        ),
        "claims_cited": all(
            not story.get("analysis", {}).get("facts")
            or (
                bool([
                    entry for entry in story.get("analysis", {}).get("evidence", [])
                    if entry.get("type") in {"fact", "official_statement", "reported_claim"}
                ])
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

    # HTML balance check
    parser = _HTMLBalance()
    try:
        parser.feed(html)
        checks["html_balanced"] = not parser.open_tags
    except Exception:
        checks["html_balanced"] = False

    checks["source_health_recorded"] = bool(source_health)
    checks["source_health_ok"] = bool(source_health) and all(
        value.get("status") in {"HEALTHY", "EMPTY", "READY", "PASS"} for value in source_health.values()
    )

    # Invariant Hard Failure Detection
    has_uncited_claims = not checks["claims_cited"]
    has_malformed_html = not checks["html_balanced"]
    has_bad_urls = not checks["source_links"]
    source_failures = [
        value for value in source_health.values()
        if value.get("status") in {"FAILED", "SOURCE_UNAVAILABLE", "QUARANTINED"}
    ]
    hard_failure = has_uncited_claims or has_malformed_html or has_bad_urls or bool(source_failures)

    # 2. Outcome metric breakdowns
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
    scores["retrieval_score"] = round(
        sum(bool(story.get("retrieved_evidence")) for story in stories) / max(1, len(stories)) * 100
    )
    scores["source_score"] = round(
        sum(value.get("status") in {"HEALTHY", "EMPTY", "READY", "PASS"} for value in source_health.values())
        / max(1, len(source_health)) * 100
    )
    scores["actionability_score"] = round(
        sum(bool(story.get("analysis", {}).get("actionable_insights")) for story in stories)
        / max(1, len(stories)) * 100
    )
    scores["intelligence_score"] = round(
        sum(scores[name] for name in ("classification_score", "theme_score", "evidence_score", "actionability_score")) / 4
    )

    # Detailed Phase 2 Outcome Metrics
    scores["microtopic_accuracy"] = scores["classification_score"]
    scores["theme_specificity"] = scores["theme_score"]
    scores["retrieval_precision"] = scores["retrieval_score"]
    scores["retrieval_recall"] = scores["evidence_score"]
    scores["provenance_integrity"] = round(
        (int(checks["claims_cited"]) * 60 + int(checks["source_links"]) * 20 + int(checks["evidence_classified"]) * 20)
    )
    scores["isolation_integrity"] = scores["classification_score"]
    scores["budget_integrity"] = 100 if all(s.get("analysis_status") != "BUDGET_OVERRUN" for s in stories) else 0
    scores["semantic_quality"] = scores["actionability_score"]
    scores["coverage_truth"] = scores["coverage_score"]

    raw_overall = round(
        sum(scores[k] for k in (
            "coverage_score", "classification_score", "theme_score", "evidence_score",
            "newsletter_score", "retrieval_score", "source_score", "actionability_score",
        )) / 8
    )

    # Rule: If any hard gate failure occurs, cap score strictly at max 59
    if hard_failure:
        scores["overall"] = min(raw_overall, 59)
        quality_status = "QUALITY_REVIEW_REQUIRED"
    else:
        scores["overall"] = raw_overall
        quality_status = "PASS" if not source_failures and all(checks.values()) and scores["overall"] >= 95 else "QUALITY_REVIEW_REQUIRED"

    return {
        "checks": checks,
        "scores": scores,
        "passed": quality_status == "PASS",
        "status": quality_status,
        "source_failures": [
            {
                "source": value.get("source"),
                "source_id": value.get("source_id"),
                "status": value.get("status"),
                "error": value.get("error"),
                "failure_reason": value.get("failure_reason"),
            }
            for value in source_failures
        ],
        "minimum_score": 95,
    }
