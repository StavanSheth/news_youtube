"""Integration tests verifying full 16-stage run lifecycle and orchestrator execution."""

from pathlib import Path
import tempfile

from intelligence.application.lifecycle import RunLifecycleStage
from intelligence.application.orchestrator import ApplicationOrchestrator
from intelligence.persistence import PersistencePaths, ProductionRepository


def test_orchestrator_16_stage_execution():
    fixture_path = Path(__file__).parents[1] / "fixtures" / "phase2_end_to_end" / "corpus.json"
    assert fixture_path.is_file()

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        paths = PersistencePaths.for_root(root)
        paths.ensure()

        orchestrator = ApplicationOrchestrator(
            root=root,
            dry_run=True,
            fixture_path=fixture_path,
        )

        md_file, html_file = orchestrator.run_edition()

        assert md_file.is_file()
        assert html_file.is_file()
        assert "# Intelligence Digest" in md_file.read_text(encoding="utf-8")
        assert "<article>" in html_file.read_text(encoding="utf-8")

        # Verify run summary in repository
        repo = ProductionRepository(paths)
        assert orchestrator.runner.summary is not None
        assert orchestrator.runner.summary.status == RunLifecycleStage.COMPLETED.value
        assert orchestrator.runner.summary.counts["stories_analyzed"] >= 1

        persisted_run = repo.get_run(orchestrator.runner.summary.run_id)
        assert persisted_run is not None
        assert persisted_run["status"] == RunLifecycleStage.COMPLETED.value


def test_orchestrator_idempotent_repeated_execution():
    fixture_path = Path(__file__).parents[1] / "fixtures" / "phase2_end_to_end" / "corpus.json"

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        orchestrator1 = ApplicationOrchestrator(root=root, dry_run=True, fixture_path=fixture_path)
        orchestrator1.run_edition()

        # Run again with same state
        orchestrator2 = ApplicationOrchestrator(root=root, dry_run=True, fixture_path=fixture_path)
        md_file2, html_file2 = orchestrator2.run_edition()

        assert md_file2.is_file()
        assert html_file2.is_file()
        assert orchestrator2.runner.summary.status == RunLifecycleStage.COMPLETED.value
