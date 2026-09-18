"""Phase 2B tests for hard eligibility filters before ranking."""

from __future__ import annotations

from intelligence.rag.eligibility import check_chunk_eligibility, filter_eligible_candidates
from intelligence.rag.query import RetrievalRequest


def test_hard_eligibility_disabled_source_and_missing_metadata():
    req = RetrievalRequest(query="test", micro_topic_id="m1", theme_id="t1")

    # Missing content_id
    bad_chunk = {"text": "some evidence", "metadata": {}}
    ok, reason = check_chunk_eligibility(bad_chunk, req)
    assert ok is False
    assert reason == "MISSING_CONTENT_ID"

    # Disabled source
    disabled_chunk = {
        "id": "c1",
        "text": "valid text",
        "metadata": {
            "content_id": "item1",
            "source_id": "banned_feed",
            "provenance": {"source_url": "https://example.test"},
        },
    }
    ok_dis, reason_dis = check_chunk_eligibility(disabled_chunk, req, disabled_sources={"banned_feed"})
    assert ok_dis is False
    assert reason_dis == "DISABLED_SOURCE"


def test_hard_eligibility_excluded_concepts():
    req = RetrievalRequest(
        query="test",
        micro_topic_id="m1",
        theme_id="t1",
        exclusion_concepts=["propaganda", "sponsored ad"],
    )
    chunk = {
        "id": "c2",
        "text": "This article is a sponsored ad for product X.",
        "metadata": {
            "content_id": "item2",
            "source_id": "feed1",
            "provenance": {"source_url": "https://example.test"},
        },
    }
    ok, reason = check_chunk_eligibility(chunk, req)
    assert ok is False
    assert "EXCLUDED_CONCEPT" in reason


def test_filter_eligible_candidates_diagnostics():
    req = RetrievalRequest(query="test", micro_topic_id="m1", theme_id="t1")
    valid = {
        "id": "c1",
        "text": "valid evidence",
        "metadata": {
            "content_id": "item1",
            "source_id": "feed1",
            "provenance": {"source_url": "https://example.test"},
        },
    }
    invalid = {"text": "no id", "metadata": {}}
    eligible, diag = filter_eligible_candidates([valid, invalid], req)
    assert len(eligible) == 1
    assert diag["rejected_count"] == 1
