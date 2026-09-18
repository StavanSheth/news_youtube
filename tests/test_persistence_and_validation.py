"""Tests for atomic persistence, run manifests, crash recovery, and validation rules."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
import tempfile

from intelligence.persistence import (
    PersistencePaths,
    RunManifest,
    atomic_write_json,
    atomic_write_text,
    is_run_resumable,
    load_checkpoint,
    read_json_safe,
    save_checkpoint,
)
from intelligence.validation.business import validate_business_rules


def test_atomic_writes_and_safe_reads():
    with tempfile.TemporaryDirectory() as tmp_dir:
        target_txt = Path(tmp_dir) / "subdir" / "test.txt"
        atomic_write_text(target_txt, "Hello atomic world")
        assert target_txt.is_file()
        assert target_txt.read_text(encoding="utf-8") == "Hello atomic world"

        target_json = Path(tmp_dir) / "subdir" / "data.json"
        data = {"key": "value", "count": 42}
        atomic_write_json(target_json, data)
        assert target_json.is_file()
        loaded = read_json_safe(target_json)
        assert loaded == data

        # Overwrite atomically
        atomic_write_json(target_json, {"key": "updated"})
        assert read_json_safe(target_json) == {"key": "updated"}

        # Non-existent safe read returns None
        assert read_json_safe(Path(tmp_dir) / "non_existent.json") is None


def test_run_manifest_lifecycle():
    with tempfile.TemporaryDirectory() as tmp_dir:
        manifest_path = Path(tmp_dir) / "run_manifest.json"
        now_iso = datetime.now(UTC).isoformat()
        manifest = RunManifest(
            run_id="run-101",
            edition_key="edition-20260918-morning",
            started_at=now_iso,
            versions={"git": "abc1234"},
            counts={"items": 10},
            budgets={"ai_calls": 5},
        )
        manifest.save(manifest_path)
        assert manifest_path.is_file()

        loaded = RunManifest.load(manifest_path)
        assert loaded is not None
        assert loaded.run_id == "run-101"
        assert loaded.edition_key == "edition-20260918-morning"
        assert loaded.status == "RUN_CREATED"

        # Mark completed and re-save
        loaded.mark_completed("COMPLETED")
        loaded.save(manifest_path)

        reloaded = RunManifest.load(manifest_path)
        assert reloaded.status == "COMPLETED"
        assert reloaded.completed_at != ""


def test_resumption_and_checkpointing():
    with tempfile.TemporaryDirectory() as tmp_dir:
        run_dir = Path(tmp_dir) / "runs" / "run-500"
        run_dir.mkdir(parents=True)

        manifest = RunManifest(
            run_id="run-500",
            edition_key="edition-test",
            started_at=datetime.now(UTC).isoformat(),
            status="RUNNING",
        )
        manifest.save(run_dir / "run_manifest.json")

        assert is_run_resumable(run_dir) is True

        # Save checkpoint
        cp_file = save_checkpoint(run_dir, "ingestion", {"ingested_count": 15})
        assert cp_file.is_file()

        cp_data = load_checkpoint(run_dir, "ingestion")
        assert cp_data == {"ingested_count": 15}

        # Mark completed -> no longer resumable as in-progress
        manifest.mark_completed()
        manifest.save(run_dir / "run_manifest.json")
        assert is_run_resumable(run_dir) is False


def test_business_rules_future_data_rejection():
    cutoff = datetime.now(UTC)
    future_time = (cutoff + timedelta(hours=2)).isoformat()
    analysis = {
        "facts": ["Future claim"],
        "evidence": [
            {"type": "fact", "text": "Something happened tomorrow", "published_at": future_time}
        ],
    }
    ok, errors = validate_business_rules(analysis, publication_cutoff=cutoff)
    assert ok is False
    assert any("exceeds publication cutoff" in e for e in errors)


def test_business_rules_no_update_integrity():
    # If status claims NO_MAJOR_UPDATE but there is a technical error, it must be rejected!
    analysis_with_error = {
        "status": "NO_MAJOR_UPDATE",
        "error": "Provider connection timeout",
        "facts": [],
    }
    ok, errors = validate_business_rules(analysis_with_error)
    assert ok is False
    assert any("Technical errors must NEVER convert to NO_MAJOR_UPDATE" in e for e in errors)


def test_persistence_paths_backward_compatibility():
    with tempfile.TemporaryDirectory() as tmp_dir:
        paths = PersistencePaths.for_root(Path(tmp_dir))
        paths.ensure()
        assert paths.data.is_dir()
        assert paths.rag.is_dir()
        assert paths.state.is_dir()
        assert paths.runs.is_dir()
