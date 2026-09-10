"""Typed Phase 1 contracts for editions, runs, timestamps, versions and provenance."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, time
from enum import StrEnum
from collections.abc import Mapping
from typing import Any
from zoneinfo import ZoneInfo

from .identity import make_content_id, make_edition_key, make_evidence_id, make_run_id, make_source_id
from .statuses import PipelineStage


class EditionType(StrEnum):
    MORNING = "MORNING"
    NIGHT = "NIGHT"


class EvidenceType(StrEnum):
    ARTICLE = "article"
    TRANSCRIPT = "transcript"
    OFFICIAL_RELEASE = "official_release"
    FILING = "filing"
    DATASET = "dataset"
    VIDEO = "video"
    OTHER = "other"


class TimestampStatus(StrEnum):
    VALID = "valid"
    MISSING = "missing"
    INVALID = "invalid"


@dataclass(frozen=True)
class VersionContract:
    application_version: str
    schema_version: str
    configuration_version: str
    taxonomy_version: str
    theme_version: str
    prompt_version: str
    scoring_version: str
    pipeline_version: str

    @classmethod
    def from_mapping(cls, values: dict[str, Any]) -> "VersionContract":
        required = (
            "application_version", "schema_version", "configuration_version", "taxonomy_version",
            "theme_version", "prompt_version", "scoring_version", "pipeline_version",
        )
        missing = [key for key in required if not str(values.get(key, "")).strip()]
        if missing:
            raise ValueError(f"Missing version contract values: {missing}")
        return cls(*(str(values[key]) for key in required))

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def require_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


@dataclass(frozen=True)
class SourceTimestamps:
    published_at: datetime | None = None
    updated_at: datetime | None = None
    retrieved_at: datetime | None = None
    published_at_status: TimestampStatus = TimestampStatus.MISSING
    updated_at_status: TimestampStatus = TimestampStatus.MISSING
    retrieved_at_status: TimestampStatus = TimestampStatus.MISSING

    def __post_init__(self) -> None:
        for name in ("published_at", "updated_at", "retrieved_at"):
            value = getattr(self, name)
            if value is not None:
                require_aware(value, name)
        if self.published_at and self.retrieved_at and self.retrieved_at < self.published_at:
            raise ValueError("retrieved_at cannot precede published_at")
        if self.published_at and self.published_at_status == TimestampStatus.MISSING:
            object.__setattr__(self, "published_at_status", TimestampStatus.VALID)
        if self.updated_at and self.updated_at_status == TimestampStatus.MISSING:
            object.__setattr__(self, "updated_at_status", TimestampStatus.VALID)
        if self.retrieved_at and self.retrieved_at_status == TimestampStatus.MISSING:
            object.__setattr__(self, "retrieved_at_status", TimestampStatus.VALID)

    @property
    def publication_status(self) -> TimestampStatus:
        """Backward-compatible alias for the publication timestamp status."""
        return self.published_at_status

    @classmethod
    def from_values(
        cls,
        published_at: Any = None,
        updated_at: Any = None,
        retrieved_at: Any = None,
        default_retrieved_at: datetime | None = None,
    ) -> "SourceTimestamps":
        published, publication_status = _parse_external_timestamp(published_at)
        updated, _ = _parse_external_timestamp(updated_at)
        retrieved, retrieved_status = _parse_external_timestamp(retrieved_at)
        if retrieved is None and retrieved_status == TimestampStatus.MISSING:
            retrieved = default_retrieved_at or datetime.now(UTC)
            retrieved_status = TimestampStatus.VALID
        if retrieved is not None and (retrieved.tzinfo is None or retrieved.utcoffset() is None):
            retrieved = retrieved.replace(tzinfo=UTC)
        if published and retrieved and retrieved < published:
            retrieved = published
        return cls(
            published,
            updated,
            retrieved,
            publication_status,
            _parse_external_timestamp(updated_at)[1],
            retrieved_status,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "retrieved_at": self.retrieved_at.isoformat() if self.retrieved_at else None,
            "published_at_status": self.published_at_status.value,
            "updated_at_status": self.updated_at_status.value,
            "retrieved_at_status": self.retrieved_at_status.value,
            "publication_status": self.publication_status.value,
        }


def _parse_external_timestamp(value: Any) -> tuple[datetime | None, TimestampStatus]:
    if value in (None, ""):
        return None, TimestampStatus.MISSING
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return None, TimestampStatus.INVALID
        return value, TimestampStatus.VALID
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None, TimestampStatus.INVALID
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None, TimestampStatus.INVALID
    return parsed, TimestampStatus.VALID


def source_timestamps_from_mapping(
    item: Mapping[str, Any], default_retrieved_at: datetime | None = None
) -> SourceTimestamps:
    metadata = item.get("metadata", {}) or {}
    return SourceTimestamps.from_values(
        item.get("published_at"),
        metadata.get("updated_at", item.get("updated_at")),
        metadata.get("retrieved_at", item.get("retrieved_at")),
        default_retrieved_at,
    )


@dataclass(frozen=True)
class EditionContext:
    edition_key: str
    edition: EditionType
    edition_date: date
    timezone: str
    publication_cutoff_local: datetime
    publication_cutoff_utc: datetime
    versions: VersionContract
    run_id: str | None = None

    def __post_init__(self) -> None:
        require_aware(self.publication_cutoff_local, "publication_cutoff_local")
        require_aware(self.publication_cutoff_utc, "publication_cutoff_utc")
        expected_key = make_edition_key(self.edition_date, self.edition.value, self.timezone)
        if self.edition_key != expected_key:
            raise ValueError("edition_key does not match the logical edition context")
        if self.publication_cutoff_local.astimezone(UTC) != self.publication_cutoff_utc:
            raise ValueError("publication cutoff local/UTC values disagree")

    def to_dict(self) -> dict[str, Any]:
        return {
            "edition_key": self.edition_key,
            "edition": self.edition.value,
            "edition_date": self.edition_date.isoformat(),
            "edition_timezone": self.timezone,
            "publication_cutoff_local": self.publication_cutoff_local.isoformat(),
            "publication_cutoff_utc": self.publication_cutoff_utc.isoformat(),
            "versions": self.versions.to_dict(),
            "run_id": self.run_id,
        }


@dataclass(frozen=True)
class RunContext:
    run_id: str
    edition_key: str
    started_at: datetime
    versions: VersionContract
    stage: PipelineStage = PipelineStage.RUN_CREATED
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_aware(self.started_at, "started_at")
        if not self.run_id or not self.edition_key:
            raise ValueError("run_id and edition_key are required")

    @classmethod
    def create(cls, edition: EditionContext, started_at: datetime, metadata: dict[str, Any] | None = None) -> "RunContext":
        require_aware(started_at, "started_at")
        return cls(make_run_id(edition.edition_key, started_at), edition.edition_key, started_at, edition.versions, metadata=metadata or {})

    def at_stage(self, stage: PipelineStage) -> "RunContext":
        return RunContext(self.run_id, self.edition_key, self.started_at, self.versions, stage, dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "edition_key": self.edition_key,
            "started_at": self.started_at.isoformat(),
            "versions": self.versions.to_dict(),
            "stage": self.stage.value,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class Provenance:
    evidence_id: str
    content_id: str
    source_id: str
    source_url: str
    evidence_type: EvidenceType
    trust_tier: int
    retrieved_at: datetime
    event_id: str | None = None
    entity_id: str | None = None
    micro_topic_id: str | None = None

    def __post_init__(self) -> None:
        if not all((self.evidence_id, self.content_id, self.source_id, self.source_url)):
            raise ValueError("provenance requires evidence_id, content_id, source_id and source_url")
        if not self.source_url.startswith(("http://", "https://")):
            raise ValueError("provenance source_url must use http(s)")
        if not 1 <= int(self.trust_tier) <= 4:
            raise ValueError("trust_tier must be between 1 and 4")
        require_aware(self.retrieved_at, "retrieved_at")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["evidence_type"] = self.evidence_type.value
        value["retrieved_at"] = self.retrieved_at.isoformat()
        return value


def provenance_from_mapping(
    item: Mapping[str, Any],
    evidence_type: EvidenceType | str,
    excerpt: str = "",
    retrieved_at: datetime | None = None,
) -> Provenance:
    metadata = item.get("metadata", {}) or {}
    source_id = str(metadata.get("source_id") or make_source_id(item.get("source", "unknown")))
    source_url = str(item.get("url", ""))
    content_id = str(
        metadata.get("content_id")
        or make_content_id(source_id, source_url, item.get("title", ""), item.get("published_at", ""), item.get("text", ""))
    )
    timestamps = source_timestamps_from_mapping(item, retrieved_at)
    resolved_type = evidence_type if isinstance(evidence_type, EvidenceType) else EvidenceType(str(evidence_type).lower()) if str(evidence_type).lower() in {entry.value for entry in EvidenceType} else EvidenceType.OTHER
    return Provenance(
        make_evidence_id(content_id, resolved_type.value, excerpt, source_url),
        content_id,
        source_id,
        source_url,
        resolved_type,
        int(metadata.get("trust_tier", 4) or 4),
        timestamps.retrieved_at or datetime.now(UTC),
        event_id=metadata.get("event_id") or None,
        entity_id=metadata.get("entity_id") or None,
        micro_topic_id=metadata.get("micro_topic_id") or None,
    )


def build_edition_context(
    edition_date: date,
    edition: EditionType | str,
    timezone: str,
    cutoff: time | datetime,
    versions: VersionContract,
) -> EditionContext:
    edition_value = EditionType(str(edition).upper())
    zone = ZoneInfo(timezone)
    if isinstance(cutoff, datetime):
        local_cutoff = cutoff if cutoff.tzinfo else cutoff.replace(tzinfo=zone)
        local_cutoff = local_cutoff.astimezone(zone)
    else:
        local_cutoff = datetime.combine(edition_date, cutoff, tzinfo=zone)
    return EditionContext(
        make_edition_key(edition_date, edition_value.value, timezone),
        edition_value,
        edition_date,
        timezone,
        local_cutoff,
        local_cutoff.astimezone(UTC),
        versions,
    )
