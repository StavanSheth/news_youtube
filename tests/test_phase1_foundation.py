from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pytest

from intelligence.config import load_config
from intelligence.contracts import (
    EditionType,
    EvidenceType,
    Provenance,
    SourceTimestamps,
    TimestampStatus,
    VersionContract,
    RunContext,
    build_edition_context,
    provenance_from_mapping,
    source_timestamps_from_mapping,
)
from intelligence.identity import (
    make_content_id,
    make_edition_key,
    make_entity_id,
    make_evidence_id,
    make_micro_topic_id,
    make_publication_id,
    make_source_id,
)
from intelligence.persistence import PersistencePaths
from intelligence import pipeline
from intelligence.production import eligible_for_edition
from intelligence.models import SourceItem
from intelligence.source_validation import validate_source_registry
from intelligence.statuses import CANONICAL_PIPELINE_ORDER, IntelligenceStatus, PipelineStage


ROOT = Path(__file__).parents[1]


def _versions() -> VersionContract:
    return VersionContract("0.1.0", "1", "1", "1", "1", "1", "1", "1")


def test_domain_specific_ids_are_deterministic_and_normalized():
    first = make_content_id("Reuters World", "HTTPS://Example.com/story/", "Headline", "", "body")
    equivalent = make_content_id("reuters world", "https://example.com/story", "Different title", "", "changed body")
    assert first == equivalent
    assert first != make_content_id("Reuters World", "https://example.com/other", "Headline", "", "body")
    assert make_content_id("source", "", "Headline", "2026-09-10T10:00:00Z", "body") == make_content_id("SOURCE", "", " headline ", "2026-09-10T10:00:00+00:00", " body ")
    assert make_source_id("Reuters World") == make_source_id("reuters   world")
    assert make_entity_id("Company", "Example Corp") == make_entity_id("company", " example corp ")
    assert make_micro_topic_id("AI", "AI", "RAG") == "micro-topic-ai-ai-rag"
    assert make_evidence_id(first, "article", "A fact", "https://example.com/story") == make_evidence_id(first, "article", " A   fact ", "https://example.com/story#fragment")
    assert make_publication_id("2026-09-10|NIGHT|Asia/Kolkata") == make_publication_id("2026-09-10|NIGHT|Asia/Kolkata")


def test_edition_and_run_identity_are_stable_across_reruns():
    edition = build_edition_context(date(2026, 9, 10), EditionType.NIGHT, "Asia/Kolkata", time(23, 59, 59), _versions())
    repeat = build_edition_context(date(2026, 9, 10), "NIGHT", "Asia/Kolkata", time(23, 59, 59), _versions())
    assert edition.edition_key == "2026-09-10|NIGHT|Asia/Kolkata"
    assert edition.edition_key == repeat.edition_key
    assert edition.publication_cutoff_local.tzinfo is not None
    assert edition.publication_cutoff_utc == datetime(2026, 9, 10, 18, 29, 59, tzinfo=UTC)
    assert make_edition_key(date(2026, 9, 10), "MORNING", "Asia/Kolkata") != edition.edition_key
    started = datetime(2026, 9, 10, 12, tzinfo=UTC)
    first_run = RunContext.create(edition, started)
    second_run = RunContext.create(repeat, started)
    assert first_run.run_id == second_run.run_id
    assert first_run.stage == PipelineStage.RUN_CREATED
    assert first_run.at_stage(PipelineStage.CLASSIFIED).stage.value == "CLASSIFIED"


def test_time_contract_separates_source_timestamps_and_rejects_naive_values():
    published = datetime(2026, 9, 10, 10, tzinfo=UTC)
    timestamps = SourceTimestamps(published, published + timedelta(hours=1), published + timedelta(hours=2))
    assert timestamps.published_at != timestamps.updated_at
    assert timestamps.retrieved_at > timestamps.published_at
    with pytest.raises(ValueError, match="timezone-aware"):
        SourceTimestamps(datetime(2026, 9, 10, 10))
    with pytest.raises(ValueError, match="cannot precede"):
        SourceTimestamps(published, retrieved_at=published - timedelta(minutes=1))


def test_provenance_separates_evidence_type_from_trust_tier():
    provenance = Provenance(
        "evidence-1", "content-1", "source-1", "https://source.test/item",
        EvidenceType.OFFICIAL_RELEASE, 1, datetime.now(UTC), micro_topic_id="micro-topic-ai-ai-rag",
    )
    record = provenance.to_dict()
    assert record["evidence_type"] == "official_release"
    assert record["trust_tier"] == 1
    with pytest.raises(ValueError):
        Provenance("e", "c", "s", "file:///unsafe", EvidenceType.ARTICLE, 1, datetime.now(UTC))
    with pytest.raises(ValueError):
        Provenance("e", "c", "s", "https://source.test", EvidenceType.ARTICLE, 5, datetime.now(UTC))


def test_versions_and_persistence_paths_are_canonical():
    config = load_config(ROOT)
    assert config.versions.taxonomy_version == "1"
    assert config.versions.to_dict() == config.versions.to_dict()
    edition = build_edition_context(date(2026, 9, 10), EditionType.MORNING, "Asia/Kolkata", time(12), config.versions)
    run = RunContext.create(edition, datetime(2026, 9, 10, 6, tzinfo=UTC))
    paths = PersistencePaths.for_root(ROOT)
    assert paths.data_file("events.json") == ROOT / "data" / "events.json"
    assert paths.edition_dir(edition).name == "2026-09-10_MORNING_Asia_Kolkata"
    assert paths.run_dir(run).parts[-1] == run.run_id


def test_shared_status_contract_contains_set_e_vocabulary():
    assert IntelligenceStatus.NO_MAJOR_UPDATE.value == "NO_MAJOR_UPDATE"
    assert IntelligenceStatus.INSUFFICIENT_EVIDENCE.value == "INSUFFICIENT_EVIDENCE"


def test_source_identity_and_run_identity_have_distinct_contracts():
    assert make_source_id("Source/A") != make_source_id("Source A")
    canonical_source = make_source_id("Source A")
    assert make_source_id(canonical_source) == canonical_source
    edition = build_edition_context(date(2026, 9, 10), EditionType.NIGHT, "Asia/Kolkata", time(23, 59, 59), _versions())
    first = RunContext.create(edition, datetime(2026, 9, 10, 12, tzinfo=UTC))
    second = RunContext.create(edition, datetime(2026, 9, 10, 12, 1, tzinfo=UTC))
    assert first.edition_key == second.edition_key == edition.edition_key
    assert first.run_id != second.run_id


def test_timestamp_states_and_edition_eligibility_are_explicit():
    floor = datetime(2026, 9, 1, tzinfo=UTC)
    cutoff = datetime(2026, 9, 10, 18, 29, 59, tzinfo=UTC)
    valid = {"published_at": "2026-09-10T10:00:00+00:00", "metadata": {}}
    missing = {"published_at": "", "metadata": {}}
    malformed = {"published_at": "not-a-timestamp", "metadata": {}}
    future = {"published_at": "2026-09-11T10:00:00+00:00", "metadata": {}}
    assert source_timestamps_from_mapping(valid).publication_status == TimestampStatus.VALID
    assert source_timestamps_from_mapping(missing).publication_status == TimestampStatus.MISSING
    assert source_timestamps_from_mapping(malformed).publication_status == TimestampStatus.INVALID
    assert eligible_for_edition(valid, floor, cutoff)
    assert not eligible_for_edition(missing, floor, cutoff)
    assert not eligible_for_edition(malformed, floor, cutoff)
    assert not eligible_for_edition(future, floor, cutoff)


def test_source_item_and_evidence_carry_validated_provenance():
    item = SourceItem(
        "item-1", "news", "A story", "https://example.test/story", "A source fact",
        published_at="2026-09-10T10:00:00+00:00",
        metadata={"retrieved_at": "2026-09-10T10:01:00+00:00", "trust_tier": 1},
    )
    payload = item.to_dict()
    assert item.timestamps.publication_status == TimestampStatus.VALID
    assert payload["provenance"]["content_id"] == item.metadata["content_id"]
    provenance = provenance_from_mapping(payload, "article", "A source fact")
    assert provenance.content_id == item.metadata["content_id"]
    assert provenance.source_id == item.metadata["source_id"]
    assert provenance.evidence_id


def test_edition_validation_and_logical_persistence_areas():
    with pytest.raises(Exception):
        build_edition_context(date(2026, 9, 10), "NIGHT", "Not/A_Timezone", time(23), _versions())
    paths = PersistencePaths.for_root(ROOT)
    assert {paths.logical_dir(name).name for name in ("raw", "normalized", "rag", "events", "entities", "state", "runs")} == {
        "raw", "normalized", "rag", "events", "entities", "state", "runs"
    }


def test_canonical_pipeline_order_is_unique_and_complete():
    assert len(CANONICAL_PIPELINE_ORDER) == len(set(CANONICAL_PIPELINE_ORDER))
    assert CANONICAL_PIPELINE_ORDER[0] == PipelineStage.COLLECT
    assert CANONICAL_PIPELINE_ORDER[-1] == PipelineStage.RUN_COMPLETED
    assert PipelineStage.PROVENANCE in CANONICAL_PIPELINE_ORDER
    assert CANONICAL_PIPELINE_ORDER.index(PipelineStage.RAG) < CANONICAL_PIPELINE_ORDER.index(PipelineStage.AI)


def test_malformed_optional_source_timestamps_are_not_promoted_to_validity():
    item = {"published_at": "2026-09-10T10:00:00+00:00", "metadata": {
        "updated_at": "bad-updated", "retrieved_at": "bad-retrieved"
    }}
    timestamps = source_timestamps_from_mapping(item)
    assert timestamps.publication_status == TimestampStatus.VALID
    assert timestamps.updated_at is None
    assert timestamps.retrieved_at is not None


def test_source_validation_applies_timeout_to_default_http_fetch(monkeypatch):
    calls = {}

    class Response:
        content = b"<rss><channel><item><title>Story</title><link>https://example.test/story</link></item></channel></rss>"

        def raise_for_status(self):
            return None

    def fake_get(url, timeout, headers):
        calls.update({"url": url, "timeout": timeout, "headers": headers})
        return Response()

    monkeypatch.setattr("intelligence.source_validation.requests.get", fake_get)
    report = validate_source_registry(
        [{"id": "source-1", "name": "Source", "enabled": True, "feed_url": "https://example.test/feed"}],
        timeout=3,
    )
    assert calls["timeout"] == 3
    assert report["source-1"]["status"] == "HEALTHY"


def test_legacy_pipeline_entry_point_delegates_to_authoritative_runner(monkeypatch, tmp_path):
    calls = {}

    def fake_run(root, dry_run=False):
        calls["root"] = root
        calls["dry_run"] = dry_run
        return (root / "digest.md", root / "digest.html")

    monkeypatch.setattr(pipeline, "run_production", fake_run)
    result = pipeline.run(tmp_path, dry_run=True)

    assert result == (tmp_path / "digest.md", tmp_path / "digest.html")
    assert calls == {"root": tmp_path, "dry_run": True}
