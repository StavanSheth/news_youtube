"""Tests for EditionRunner lifecycle management and summary persistence."""

from pathlib import Path
import tempfile

from intelligence.application.edition_runner import EditionRunner
from intelligence.application.lifecycle import RunLifecycleStage
from intelligence.contracts import VersionContract
from intelligence.infrastructure.clock import SystemClock
from intelligence.persistence import PersistencePaths, ProductionRepository


def test_edition_runner_lifecycle_and_persistence():
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        paths = PersistencePaths.for_root(root)
        paths.ensure()
        repo = ProductionRepository(paths)
        clock = SystemClock()
        versions = VersionContract("1.0.0", "1.0.0", "1.0.0", "1.0.0", "1.0.0", "1.0.0", "1.0.0", "1.0.0")

        runner = EditionRunner(
            settings={"edition": {"type": "MORNING", "timezone": "UTC"}},
            paths=paths,
            repository=repo,
            versions=versions,
        )

        edition_ctx, run_ctx = runner.start(clock.now_utc())
        assert edition_ctx.edition.value == "MORNING"
        assert run_ctx.run_id
        assert runner.summary.status == RunLifecycleStage.INITIALIZING.value

        # Finalize
        summary = runner.finalize(
            status=RunLifecycleStage.COMPLETED.value,
            counts={"collected": 10, "analyzed": 5},
            budgets={"tokens": 1200},
        )
        assert summary.status == RunLifecycleStage.COMPLETED.value
        assert summary.counts["collected"] == 10

        # Check file was persisted
        persisted = repo.get_run(run_ctx.run_id)
        assert persisted is not None
        assert persisted["status"] == RunLifecycleStage.COMPLETED.value
        assert persisted["counts"]["analyzed"] == 5


def test_edition_runner_failure():
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        paths = PersistencePaths.for_root(root)
        paths.ensure()
        repo = ProductionRepository(paths)
        versions = VersionContract("1.0.0", "1.0.0", "1.0.0", "1.0.0", "1.0.0", "1.0.0", "1.0.0", "1.0.0")

        runner = EditionRunner(
            settings={"edition": {"type": "NIGHT", "timezone": "UTC"}},
            paths=paths,
            repository=repo,
            versions=versions,
        )
        _, run_ctx = runner.start()
        summary = runner.fail("Ingestion network unreachable")
        assert summary.status == RunLifecycleStage.FAILED.value
        assert any("Ingestion network unreachable" in str(f) for f in summary.failure_summary)

        persisted = repo.get_run(run_ctx.run_id)
        assert persisted["status"] == RunLifecycleStage.FAILED.value
