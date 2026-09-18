"""Tests for publication idempotency, delivery state machine, and archive integrity."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from intelligence.publication.archive import archive_edition_run
from intelligence.publication.delivery import DeliveryRecord, DeliveryState
from intelligence.publication.idempotency import IdempotencyLedger, PublicationIdentity


def test_publication_identity_is_deterministic():
    items = [
        {"id": "art-1", "url": "https://example.test/1", "published_at": "2026-09-18T10:00:00Z"},
        {"id": "art-2", "url": "https://example.test/2", "published_at": "2026-09-18T11:00:00Z"},
    ]
    id1 = PublicationIdentity.create(
        edition_date=date(2026, 9, 18),
        edition_type="NIGHT",
        timezone="Asia/Kolkata",
        content_items=items,
        rendered_content="# Digest Content",
    )
    id2 = PublicationIdentity.create(
        edition_date=date(2026, 9, 18),
        edition_type="NIGHT",
        timezone="Asia/Kolkata",
        content_items=items,
        rendered_content="# Digest Content",
    )
    assert id1.edition_key == "2026-09-18|NIGHT|Asia/Kolkata"
    assert id1.publication_id == id2.publication_id
    assert id1.content_hash == id2.content_hash
    assert id1.artifact_hash == id2.artifact_hash


def test_idempotency_ledger_prevents_duplicate_publication():
    ledger = IdempotencyLedger()
    identity = PublicationIdentity.create(
        edition_date=date(2026, 9, 18),
        edition_type="MORNING",
        timezone="Asia/Kolkata",
        content_items=[{"id": "1", "url": "https://test.test", "published_at": "2026-09-18T06:00:00Z"}],
    )
    assert ledger.is_already_published(identity.edition_key) is False

    ledger.record_publication(identity, delivery_status="DELIVERY_CONFIRMED")
    assert ledger.is_already_published(identity.edition_key) is True


def test_delivery_record_lifecycle():
    rec = DeliveryRecord(edition_key="2026-09-18|NIGHT|Asia/Kolkata", run_id="run-123")
    assert rec.delivery_status == DeliveryState.NOT_ATTEMPTED

    rec.confirm()
    assert rec.delivery_status == DeliveryState.DELIVERY_CONFIRMED
    assert rec.confirmed_at is not None

    rec2 = DeliveryRecord(edition_key="2026-09-18|NIGHT|Asia/Kolkata", run_id="run-456")
    rec2.fail("SMTP Authentication Error")
    assert rec2.delivery_status == DeliveryState.DELIVERY_FAILED
    assert rec2.error_message == "SMTP Authentication Error"


def test_archive_edition_run_creates_deterministic_files(tmp_path: Path):
    target = archive_edition_run(
        tmp_path,
        edition_key="2026-09-18|NIGHT|Asia/Kolkata",
        run_id="abc12345",
        artifacts={
            "digest.md": "# Markdown",
            "digest.html": "<html></html>",
            "quality.json": {"passed": True, "scores": {"overall": 100}},
        },
    )
    assert target.is_dir()
    assert (target / "digest.md").read_text(encoding="utf-8") == "# Markdown"
    assert (target / "quality.json").is_file()
