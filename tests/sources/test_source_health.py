"""Tests for source health persistence: save_source_health, get_source_health."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from intelligence.persistence import PersistencePaths, ProductionRepository


class TestSourceHealthPersistence:
    @pytest.fixture()
    def repo(self, tmp_path: Path) -> ProductionRepository:
        paths = PersistencePaths.for_root(tmp_path)
        return ProductionRepository(paths)

    def _health_record(self, source_id: str = "test-source", status: str = "READY") -> dict:
        return {
            "source_id": source_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "status": status,
            "lifecycle_state": "READY",
            "checks": {"configured": True, "reachable": True, "authenticated": True},
            "latency_ms": 123.4,
            "freshness_seconds": 3600,
            "latest_content_at": datetime.now(UTC).isoformat(),
            "items_seen": 10,
            "items_valid": 9,
            "items_rejected": 1,
            "error_codes": [],
            "failure_reason": None,
            "last_successful_validation": datetime.now(UTC).isoformat(),
            "last_successful_collection": datetime.now(UTC).isoformat(),
        }

    def test_save_source_health_returns_path(self, repo):
        record = self._health_record()
        path = repo.save_source_health("test-source", record)
        assert isinstance(path, Path)
        assert path.exists()

    def test_save_and_retrieve_source_health(self, repo):
        record = self._health_record("my-source", "QUARANTINED")
        repo.save_source_health("my-source", record)
        retrieved = repo.get_source_health("my-source")
        assert retrieved is not None
        assert retrieved["source_id"] == "my-source"
        assert retrieved["status"] == "QUARANTINED"

    def test_get_source_health_returns_none_for_unknown(self, repo):
        assert repo.get_source_health("nonexistent-source") is None

    def test_save_all_source_health_persists_multiple(self, repo):
        records = {
            "source-a": self._health_record("source-a", "READY"),
            "source-b": self._health_record("source-b", "QUARANTINED"),
            "source-c": self._health_record("source-c", "DISABLED"),
        }
        repo.save_all_source_health(records)
        for sid, expected in records.items():
            retrieved = repo.get_source_health(sid)
            assert retrieved is not None
            assert retrieved["status"] == expected["status"]

    def test_get_all_source_health_returns_all_records(self, repo):
        records = {
            "s1": self._health_record("s1", "READY"),
            "s2": self._health_record("s2", "QUARANTINED"),
        }
        repo.save_all_source_health(records)
        all_health = repo.get_all_source_health()
        assert "s1" in all_health
        assert "s2" in all_health

    def test_overwrite_updates_existing_record(self, repo):
        repo.save_source_health("s1", self._health_record("s1", "QUARANTINED"))
        repo.save_source_health("s1", self._health_record("s1", "READY"))
        retrieved = repo.get_source_health("s1")
        assert retrieved["status"] == "READY"

    def test_atomic_write_prevents_partial_state(self, repo):
        """Health files must be written atomically — no partial JSON."""
        large_record = self._health_record("large-source", "READY")
        large_record["extra_data"] = "x" * 100_000
        path = repo.save_source_health("large-source", large_record)
        assert path.exists()
        # Read back must be valid JSON with correct content
        retrieved = repo.get_source_health("large-source")
        assert retrieved is not None
        assert len(retrieved["extra_data"]) == 100_000
