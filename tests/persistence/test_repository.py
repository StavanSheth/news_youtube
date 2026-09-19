"""Tests for authoritative ProductionRepository enforcing standard persistence tree."""

from pathlib import Path
import tempfile

from intelligence.persistence import PersistencePaths, ProductionRepository, RunManifest


def test_production_repository_tree_and_atomic_saves():
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        paths = PersistencePaths.for_root(root)
        repo = ProductionRepository(paths)

        # Verify all logical persistence subdirectories exist
        assert repo.raw_dir.is_dir()
        assert repo.normalized_dir.is_dir()
        assert repo.rag_dir.is_dir()
        assert repo.events_dir.is_dir()
        assert repo.entities_dir.is_dir()
        assert repo.state_dir.is_dir()
        assert repo.runs_dir.is_dir()
        assert repo.archive_dir.is_dir()

        # Save source
        src_path = repo.save_source("source-bbc", {"name": "BBC", "trust_tier": 1})
        assert src_path.is_file()

        # Save content
        cnt_path = repo.save_content("content-001", {"title": "Article 1", "text": "Body"})
        assert cnt_path.is_file()
        assert repo.get_content("content-001") == {"title": "Article 1", "text": "Body"}

        # Save evidence
        ev_path = repo.save_evidence("ev-001", {"text": "Fact statement"})
        assert ev_path.is_file()

        # Save event
        evnt_path = repo.save_event("event-001", {"name": "Conference"})
        assert evnt_path.is_file()

        # Save entity
        ent_path = repo.save_entity("entity-google", {"name": "Google"})
        assert ent_path.is_file()

        # Save run manifest
        manifest = RunManifest(run_id="run-999", edition_key="ed-01", started_at="2026-09-18T00:00:00+00:00")
        run_path = repo.save_run("run-999", manifest)
        assert run_path.is_file()
        assert repo.get_run("run-999")["run_id"] == "run-999"

        # Save analysis
        an_path = repo.save_analysis("analysis-001", {"confidence": 0.8})
        assert an_path.is_file()

        # Save budget snapshot
        bdg_path = repo.save_budget_snapshot("run-999", {"tokens_used": 500})
        assert bdg_path.is_file()

        # Save delivery
        del_path = repo.save_delivery("delivery-001", {"status": "SENT"})
        assert del_path.is_file()
