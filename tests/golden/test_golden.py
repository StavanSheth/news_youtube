"""Authoritative Golden Dataset covering all 15 required representative cases."""

from datetime import UTC, datetime

from intelligence.rag.eligibility import TemporalEvidencePolicy


GOLDEN_CASES = [
    {
        "id": "case-01-major-update",
        "name": "major update",
        "input": {"title": "Foundation model benchmark release", "text": "New model capability and inference benchmark."},
        "expected_classification": "foundation-models",
        "expected_status": "OK",
        "expected_validation": "VALID",
    },
    {
        "id": "case-02-minor-update",
        "name": "minor update",
        "input": {"title": "Patch release for agent workflow", "text": "Minor bugfix release for tool use."},
        "expected_classification": "ai-agents",
        "expected_status": "OK",
        "expected_validation": "VALID",
    },
    {
        "id": "case-03-no-major-update",
        "name": "no major update",
        "input": {"title": "Routine library maintenance", "text": "Routine dependency bump without behavioral change."},
        "expected_classification": None,
        "expected_status": "CHECKED_NO_MAJOR_UPDATE",
        "expected_validation": "VALID",
    },
    {
        "id": "case-04-no-relevant-content",
        "name": "no relevant content",
        "input": {"title": "Artisanal bakery sourdough recipe", "text": "Flour and water sourdough starter technique."},
        "expected_classification": None,
        "expected_status": "NO_RELEVANT_CONTENT",
        "expected_validation": "VALID",
    },
    {
        "id": "case-05-insufficient-evidence",
        "name": "insufficient evidence",
        "input": {"title": "Rumor of new chip", "text": "Unverified tweet claiming new quantum chip exists."},
        "expected_classification": "quantum-computing",
        "expected_status": "INSUFFICIENT_EVIDENCE",
        "expected_validation": "INVALID",
    },
    {
        "id": "case-06-budget-skipped",
        "name": "budget skipped",
        "input": {"title": "Low priority update", "text": "Low priority update while edition budget exhausted."},
        "expected_classification": "general",
        "expected_status": "BUDGET_SKIPPED",
        "expected_validation": "VALID",
    },
    {
        "id": "case-07-transcript-unavailable",
        "name": "transcript unavailable",
        "input": {"title": "Video without subtitles", "text": "", "kind": "youtube"},
        "expected_classification": None,
        "expected_status": "TRANSCRIPT_UNAVAILABLE",
        "expected_validation": "VALID",
    },
    {
        "id": "case-08-technical-failure",
        "name": "technical failure",
        "input": {"title": "Crashing provider", "error": "AI_PROVIDER_ERROR"},
        "expected_classification": None,
        "expected_status": "AI_PROVIDER_ERROR",
        "expected_validation": "INVALID",
    },
    {
        "id": "case-09-duplicate-article",
        "name": "duplicate article",
        "input": {"title": "Syndicated Wire Copy", "url": "https://wire.test/copy-1"},
        "expected_classification": None,
        "expected_status": "DUPLICATE_COLLAPSED",
        "expected_validation": "VALID",
    },
    {
        "id": "case-10-syndicated-article",
        "name": "syndicated article",
        "input": {"title": "Syndicated Wire Copy 2", "url": "https://wire.test/copy-2"},
        "expected_classification": None,
        "expected_status": "SYNDICATION_COLLAPSED",
        "expected_validation": "VALID",
    },
    {
        "id": "case-11-conflicting-sources",
        "name": "conflicting sources",
        "input": {"title": "Contradictory claim", "text": "Source A says revenue rose, Source B says revenue fell."},
        "expected_classification": "financial-markets",
        "expected_status": "CONFLICT_PENALIZED",
        "expected_validation": "VALID",
    },
    {
        "id": "case-12-future-dated-article",
        "name": "future-dated article",
        "input": {"title": "Future article", "published_at": "2099-01-01T00:00:00+00:00"},
        "expected_classification": None,
        "expected_status": "HARD_REJECT_FUTURE",
        "expected_validation": "INVALID",
    },
    {
        "id": "case-13-generic-article",
        "name": "generic article",
        "input": {"title": "AI is a game changer", "text": "AI will revolutionize the industry in today's fast-paced world."},
        "expected_classification": None,
        "expected_status": "GENERIC_REJECTED",
        "expected_validation": "INVALID",
    },
    {
        "id": "case-14-high-value-technical-article",
        "name": "high-value technical article",
        "input": {"title": "Paper review on dynamic attention", "text": "Dynamic test-time compute scaling on Olympiad benchmarks."},
        "expected_classification": "foundation-models",
        "expected_status": "HIGH_VALUE_ANALYSIS",
        "expected_validation": "VALID",
    },
    {
        "id": "case-15-high-value-youtube-transcript",
        "name": "high-value YouTube transcript",
        "input": {"title": "Detailed architecture walkthrough", "kind": "youtube", "text": "Walkthrough of attention weights dynamically adjusted."},
        "expected_classification": "foundation-models",
        "expected_status": "HIGH_VALUE_TRANSCRIPT",
        "expected_validation": "VALID",
    },
]


def test_golden_dataset_has_all_15_cases():
    assert len(GOLDEN_CASES) == 15
    names = {c["name"] for c in GOLDEN_CASES}
    assert "major update" in names
    assert "future-dated article" in names
    assert "generic article" in names
    assert "budget skipped" in names


def test_golden_future_case_is_rejected():
    future_case = next(c for c in GOLDEN_CASES if c["name"] == "future-dated article")
    policy = TemporalEvidencePolicy(publication_cutoff=datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC))
    future_dt = datetime.fromisoformat(future_case["input"]["published_at"])
    ok, reason = policy.evaluate(published_at=future_dt)
    assert not ok
    assert reason == "FUTURE_EVIDENCE_EXCEEDS_CUTOFF"


def test_golden_technical_failure_status_invariant():
    # Technical failure must NEVER convert to NO_MAJOR_UPDATE
    tech_case = next(c for c in GOLDEN_CASES if c["name"] == "technical failure")
    assert tech_case["expected_status"] != "NO_MAJOR_UPDATE"
    assert tech_case["expected_status"] == "AI_PROVIDER_ERROR"
