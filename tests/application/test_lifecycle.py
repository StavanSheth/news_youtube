"""Tests for explicit run lifecycle stages and RunSummary contracts."""

from intelligence.application.lifecycle import RunLifecycleStage, RunSummary


def test_lifecycle_stages_coverage():
    expected_stages = [
        "CREATED", "INITIALIZING", "COLLECTING", "NORMALIZING", "FILTERING",
        "DEDUPLICATING", "CLASSIFYING", "RETRIEVING", "ANALYZING", "VALIDATING",
        "ENRICHING", "ASSEMBLING", "RENDERING", "DELIVERING", "COMPLETED",
        "FAILED", "PARTIAL",
    ]
    for stage in expected_stages:
        assert stage in [s.value for s in RunLifecycleStage]


def test_run_summary_lifecycle_and_serialization():
    summary = RunSummary(
        run_id="run-test-01",
        edition_id="edition-2026-morning",
        started_at="2026-09-18T06:00:00+00:00",
        config_version="1.2.0",
        taxonomy_version="1.0.0",
        prompt_version="2.0.0",
        pipeline_version="2.1.0",
        counts={"items_collected": 20, "items_filtered": 15},
        budget_usage={"tokens": 1500, "cost": 0.002},
    )
    assert summary.status == RunLifecycleStage.CREATED.value

    # Mark completed
    summary.mark_completed(RunLifecycleStage.COMPLETED.value)
    assert summary.status == RunLifecycleStage.COMPLETED.value

    # To dict and from dict
    data = summary.to_dict()
    assert data["run_id"] == "run-test-01"
    assert data["counts"]["items_collected"] == 20
    assert data["budget_usage"]["tokens"] == 1500

    reconstructed = RunSummary.from_dict(data)
    assert reconstructed.run_id == summary.run_id
    assert reconstructed.edition_id == summary.edition_id
    assert reconstructed.status == RunLifecycleStage.COMPLETED.value


def test_run_summary_failure_recording():
    summary = RunSummary(
        run_id="run-fail-01",
        edition_id="edition-test",
        started_at="2026-09-18T06:00:00+00:00",
    )
    summary.mark_failed("AI provider connection error")
    assert summary.status == RunLifecycleStage.FAILED.value
    assert len(summary.failure_summary) == 1
    assert "connection error" in str(summary.failure_summary[0])
