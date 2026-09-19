"""Authoritative Source contracts, lifecycle state machine, and production registry."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import feedparser
import requests
import yaml

from .models import SourceItem


class SourceRole(StrEnum):
    NEWS = "NEWS"
    VIDEO = "VIDEO"
    RESEARCH = "RESEARCH"
    OFFICIAL = "OFFICIAL"
    GOVERNMENT = "GOVERNMENT"
    COMPANY = "COMPANY"
    GITHUB = "GITHUB"
    MARKET = "MARKET"
    SPECIALIST = "SPECIALIST"


class SourceLifecycleState(StrEnum):
    REGISTERED = "REGISTERED"
    CONFIGURED = "CONFIGURED"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    AUTHENTICATED = "AUTHENTICATED"
    REACHABILITY_FAILED = "REACHABILITY_FAILED"
    COLLECTION_FAILED = "COLLECTION_FAILED"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    STALE = "STALE"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    CONTENT_UNAVAILABLE = "CONTENT_UNAVAILABLE"
    ROLE_INVALID = "ROLE_INVALID"
    MAPPING_INVALID = "MAPPING_INVALID"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    QUARANTINED = "QUARANTINED"
    DISABLED = "DISABLED"
    READY = "READY"


class SourceAcceptanceStatus(StrEnum):
    PASS = "PASS"
    READY = "READY"
    DISABLE = "DISABLE"
    DISABLED = "DISABLED"
    QUARANTINE = "QUARANTINE"
    QUARANTINED = "QUARANTINED"


@dataclass(frozen=True)
class FreshnessPolicy:
    max_age_hours: int = 48
    stale_after_hours: int = 72
    schedule: str = "daily"

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> FreshnessPolicy:
        if not data:
            return cls()
        return cls(
            max_age_hours=int(data.get("max_age_hours", 48)),
            stale_after_hours=int(data.get("stale_after_hours", 72)),
            schedule=str(data.get("schedule", "daily")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CollectionBudget:
    max_items_per_run: int = 25
    max_pages: int = 1
    max_bytes: int = 5_000_000
    timeout_seconds: int = 15
    retry_count: int = 2

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> CollectionBudget:
        if not data:
            return cls()
        return cls(
            max_items_per_run=int(data.get("max_items_per_run", 25)),
            max_pages=int(data.get("max_pages", 1)),
            max_bytes=int(data.get("max_bytes", 5_000_000)),
            timeout_seconds=int(data.get("timeout_seconds", 15)),
            retry_count=int(data.get("retry_count", 2)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ComplianceErrorCode(StrEnum):
    LICENSE_UNKNOWN = "LICENSE_UNKNOWN"
    RETENTION_UNDEFINED = "RETENTION_UNDEFINED"
    STORAGE_NOT_PERMITTED = "STORAGE_NOT_PERMITTED"
    ATTRIBUTION_REQUIRED = "ATTRIBUTION_REQUIRED"


@dataclass(frozen=True)
class SourceContract:
    id: str
    name: str
    type: str
    role: SourceRole
    trust_tier: int
    region: str
    country: str
    domains: tuple[str, ...]
    topics: tuple[str, ...]
    micro_topics: tuple[str, ...]
    collection_method: str
    url: str
    enabled: bool = False
    freshness_policy: FreshnessPolicy = field(default_factory=FreshnessPolicy)
    extraction_capability: str = "article_body"
    authentication_required: bool = False
    authentication_env_var: str | None = None
    attribution_required: bool = True
    storage_permission: bool = True
    content_storage_allowed: bool = True
    raw_content_allowed: bool = True
    derived_content_allowed: bool = True
    retention_policy: str = "REQUIRED"
    license_status: str = "PERMITTED"
    fallback_behavior: str = "DEGRADE"
    budgets: CollectionBudget = field(default_factory=CollectionBudget)
    fields_list: tuple[str, ...] = ("title", "summary", "published_at", "url")
    refresh: str = "daily"
    priority: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate_compliance(self) -> tuple[bool, list[str]]:
        """Validate legal, license, storage, and retention compliance."""
        errors: list[str] = []
        lic = str(self.license_status).upper()
        if lic in ("LICENSE_UNKNOWN", "UNKNOWN", "UNRESOLVED", "DENIED", "RESTRICTED_DENIED"):
            errors.append(ComplianceErrorCode.LICENSE_UNKNOWN.value)
        ret = str(self.retention_policy).upper()
        if ret in ("RETENTION_UNDEFINED", "UNDEFINED", "UNKNOWN", "NONE"):
            errors.append(ComplianceErrorCode.RETENTION_UNDEFINED.value)
        if not self.storage_permission or not self.content_storage_allowed:
            errors.append(ComplianceErrorCode.STORAGE_NOT_PERMITTED.value)
        return len(errors) == 0, errors

    @property
    def source_id(self) -> str:
        return self.id

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> SourceContract:
        sid = str(data.get("id") or data.get("source_id") or data.get("name", "unknown")).strip()
        name = str(data.get("name", sid)).strip()
        stype = str(data.get("type") or data.get("source_type") or "rss").lower().strip()
        
        # Determine source role
        role_raw = str(data.get("role") or data.get("source_role", "")).upper().strip()
        if not role_raw:
            if stype in ("youtube", "video"):
                role = SourceRole.VIDEO
            elif "gov" in sid or "ministry" in sid or "white-house" in sid:
                role = SourceRole.GOVERNMENT
            elif "sec" in sid or "fed" in sid or "ecb" in sid or "bank" in sid:
                role = SourceRole.OFFICIAL
            elif "cern" in sid or "csiro" in sid or "nist" in sid:
                role = SourceRole.RESEARCH
            else:
                role = SourceRole.NEWS
        else:
            try:
                role = SourceRole(role_raw)
            except ValueError:
                role = SourceRole.NEWS

        trust_tier = int(data.get("trust_tier", 2))
        region = str(data.get("region", "global")).strip()
        country = str(data.get("country", "GLOBAL")).strip()
        domains = tuple(str(d).strip() for d in data.get("domains", []))
        topics = tuple(str(t).strip() for t in data.get("topics", []))
        micro_topics = tuple(str(m).strip() for m in data.get("micro_topics", []))
        collection_method = str(data.get("collection_method") or stype).strip()
        url = str(data.get("feed_url") or data.get("url") or data.get("api_endpoint", "")).strip()
        enabled = bool(data.get("enabled", False))

        # Sub-contracts
        freshness = FreshnessPolicy.from_mapping(data.get("freshness_policy"))
        budgets = CollectionBudget.from_mapping(data.get("budgets"))

        return cls(
            id=sid,
            name=name,
            type=stype,
            role=role,
            trust_tier=trust_tier,
            region=region,
            country=country,
            domains=domains,
            topics=topics,
            micro_topics=micro_topics,
            collection_method=collection_method,
            url=url,
            enabled=enabled,
            freshness_policy=freshness,
            extraction_capability=str(data.get("extraction_capability", "article_body")),
            authentication_required=bool(data.get("authentication_required", False)),
            authentication_env_var=data.get("authentication_env_var") or None,
            attribution_required=bool(data.get("attribution_required", True)),
            storage_permission=bool(data.get("storage_permission", True)),
            content_storage_allowed=bool(data.get("content_storage_allowed", True)),
            raw_content_allowed=bool(data.get("raw_content_allowed", True)),
            derived_content_allowed=bool(data.get("derived_content_allowed", True)),
            retention_policy=str(data.get("retention_policy", "REQUIRED")),
            license_status=str(data.get("license_status", "PERMITTED")),
            fallback_behavior=str(data.get("fallback_behavior", "DEGRADE")),
            budgets=budgets,
            fields_list=tuple(str(f) for f in data.get("fields", ["title", "summary", "published_at", "url"])),
            refresh=str(data.get("refresh", "daily")),
            priority=float(data.get("priority", 1.0)),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["role"] = self.role.value
        result["domains"] = list(self.domains)
        result["topics"] = list(self.topics)
        result["micro_topics"] = list(self.micro_topics)
        result["fields"] = list(self.fields_list)
        del result["fields_list"]
        return result


@dataclass
class SourceAcceptanceResult:
    source_id: str
    run_id: str
    checked_at: str
    configured: bool
    reachable: bool
    authenticated: bool
    collection_success: bool
    response_valid: bool
    freshness_valid: bool
    schema_valid: bool
    content_extractable: bool
    role_valid: bool
    mapping_valid: bool
    evidence_valid: bool
    license_valid: bool
    retention_valid: bool
    status: str
    failure_codes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    items_seen: int = 0
    items_valid: int = 0
    items_rejected: int = 0
    latest_content_at: str | None = None
    oldest_content_at: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        return self.status in (SourceAcceptanceStatus.READY.value, SourceAcceptanceStatus.PASS.value)

    @property
    def is_quarantined(self) -> bool:
        return self.status in (SourceAcceptanceStatus.QUARANTINE.value, SourceAcceptanceStatus.QUARANTINED.value)

    @property
    def is_disabled(self) -> bool:
        return self.status in (SourceAcceptanceStatus.DISABLE.value, SourceAcceptanceStatus.DISABLED.value)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["checks"] = {
            "configured": self.configured,
            "authenticated": self.authenticated,
            "reachable": self.reachable,
            "fresh": self.freshness_valid,
            "schema_valid": self.schema_valid,
            "extractable": self.content_extractable,
            "role_valid": self.role_valid,
            "mapping_valid": self.mapping_valid,
            "evidence_useful": self.evidence_valid,
        }
        return data


class ProductionSourceRegistry:
    """Canonical registry managing configured sources and their acceptance lifecycle."""

    def __init__(self, sources: list[SourceContract]) -> None:
        self._sources: dict[str, SourceContract] = {s.id: s for s in sources}
        self._acceptance: dict[str, SourceAcceptanceResult] = {}

    @classmethod
    def load_from_config(cls, config_dir: Path) -> ProductionSourceRegistry:
        sources: list[SourceContract] = []
        seen_ids: set[str] = set()

        # 1. Load RSS / primary source registry
        registry_file = config_dir / "source_registry.yaml"
        if registry_file.is_file():
            content = yaml.safe_load(registry_file.read_text(encoding="utf-8")) or {}
            for item in content.get("sources", []):
                contract = SourceContract.from_mapping(item)
                if contract.id in seen_ids:
                    raise ValueError(f"Duplicate source_id in registry: {contract.id}")
                seen_ids.add(contract.id)
                sources.append(contract)

        # 2. Load YouTube channels registry
        channels_file = config_dir / "channels.yaml"
        if channels_file.is_file():
            content = yaml.safe_load(channels_file.read_text(encoding="utf-8")) or {}
            for ch in content.get("channels", []):
                cid = ch.get("id")
                if not cid:
                    continue
                data = {
                    "id": cid,
                    "name": ch.get("name", cid),
                    "type": "youtube",
                    "role": "VIDEO",
                    "trust_tier": ch.get("trust_tier", 2),
                    "region": ch.get("region", "global"),
                    "country": ch.get("country", "GLOBAL"),
                    "domains": ch.get("domains", ["artificial-intelligence"]),
                    "topics": ch.get("topics", ["foundation-models"]),
                    "micro_topics": ch.get("micro_topics", []),
                    "collection_method": "youtube_api",
                    "url": f"https://www.youtube.com/channel/{cid}",
                    "enabled": ch.get("enabled", False),
                    "authentication_required": True,
                    "authentication_env_var": "YOUTUBE_API_KEY",
                    "priority": ch.get("priority", 1.0),
                    "metadata": ch,
                }
                contract = SourceContract.from_mapping(data)
                if contract.id not in seen_ids:
                    seen_ids.add(contract.id)
                    sources.append(contract)

        return cls(sources)

    def get_source(self, source_id: str) -> SourceContract:
        if source_id not in self._sources:
            raise KeyError(f"Source not found: {source_id}")
        return self._sources[source_id]

    @property
    def sources(self) -> list[SourceContract]:
        return self.all_sources()

    def all_sources(self) -> list[SourceContract]:
        return list(self._sources.values())

    def enabled_sources(self) -> list[SourceContract]:
        return [s for s in self._sources.values() if s.enabled]

    def ready_sources(self) -> list[SourceContract]:
        return [
            s for s in self._sources.values()
            if s.id in self._acceptance and self._acceptance[s.id].is_ready
        ]

    def quarantined_sources(self) -> list[SourceContract]:
        return [
            s for s in self._sources.values()
            if s.id in self._acceptance and self._acceptance[s.id].is_quarantined
        ]

    def update_acceptance(self, results: dict[str, SourceAcceptanceResult]) -> None:
        self._acceptance.update(results)

    def get_acceptance(self, source_id: str) -> SourceAcceptanceResult | None:
        return self._acceptance.get(source_id)


# Backward-compatible API for existing discovery code
def _youtube_get(path: str, params: dict, api_key: str) -> dict:
    response = requests.get(
        f"https://www.googleapis.com/youtube/v3/{path}",
        params={**params, "key": api_key},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def discover_youtube(
    channels: list[dict], topics: list[dict] | None = None, api_key: str = "",
    keyword_limit: int = 0, allow_global_discovery: bool = False,
) -> list[SourceItem]:
    """Ingest configured YouTube channels via uploads playlist."""

    if not api_key:
        api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if not api_key:
        return []

    items: list[SourceItem] = []
    seen: set[str] = set()
    for channel in channels:
        if not channel.get("enabled") or not channel.get("id"):
            continue
        try:
            details = _youtube_get("channels", {"part": "contentDetails", "id": channel["id"]}, api_key)
            for detail in details.get("items", []):
                uploads = detail["contentDetails"]["relatedPlaylists"]["uploads"]
                listing = _youtube_get(
                    "playlistItems",
                    {"part": "snippet,contentDetails", "playlistId": uploads, "maxResults": 15},
                    api_key,
                )
                for entry in listing.get("items", []):
                    video_id = entry["contentDetails"].get("videoId")
                    if video_id and video_id not in seen:
                        seen.add(video_id)
                        snippet = entry["snippet"]
                        items.append(_video_item(video_id, snippet, channel.get("priority", 1), channel))
        except Exception:
            continue

    if not allow_global_discovery or keyword_limit <= 0 or not topics:
        return items

    for topic in topics:
        query = " ".join(topic.get("keywords", [])[:2])
        if not query:
            continue
        try:
            listing = _youtube_get(
                "search",
                {
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "order": "date",
                    "maxResults": keyword_limit,
                },
                api_key,
            )
            for entry in listing.get("items", []):
                video_id = entry["id"].get("videoId")
                if video_id and video_id not in seen:
                    seen.add(video_id)
                    items.append(_video_item(video_id, entry["snippet"], 1.0))
        except Exception:
            continue
    return items


def _video_item(video_id: str, snippet: dict, priority: float, channel: dict | None = None) -> SourceItem:
    from .ingestion import transcript

    transcript_text, transcript_metadata = transcript(video_id, ["en"])
    title = snippet.get("title", "Untitled video")
    content_type = "podcast" if any(token in title.lower() for token in ("podcast", "interview", "conversation")) else "video"
    return SourceItem(
        id=video_id,
        kind="youtube",
        title=title,
        url=f"https://www.youtube.com/watch?v={video_id}",
        text=f"{snippet.get('title', '')}\n{snippet.get('description', '')}\n{transcript_text}",
        published_at=snippet.get("publishedAt", ""),
        source=snippet.get("channelTitle", "YouTube"),
        priority=float(priority),
        metadata={
            **transcript_metadata,
            "content_stream": "video",
            "content_type": content_type,
            "region": (channel or {}).get("region", "global"),
            "country": (channel or {}).get("country", "GLOBAL"),
            "source_id": (channel or {}).get("id", video_id),
            "retrieved_at": datetime.now(UTC).isoformat(),
            "updated_at": snippet.get("publishedAt", ""),
        },
    )


def discover_rss(feeds: list[dict]) -> Iterable[SourceItem]:
    for feed in feeds:
        if feed.get("enabled", True) is False:
            continue
        parsed = feedparser.parse(feed.get("url") or feed.get("feed_url", ""))
        for entry in parsed.entries:
            url = entry.get("link", "")
            if not url:
                continue
            stable_id = entry.get("id") or hashlib.sha256(url.encode()).hexdigest()
            published = entry.get("published", "")
            try:
                published = datetime(*entry.published_parsed[:6], tzinfo=UTC).isoformat()
            except (AttributeError, TypeError):
                pass
            yield SourceItem(
                id=stable_id,
                kind="news",
                title=entry.get("title", "Untitled article"),
                url=url,
                text=f"{entry.get('title', '')}\n{entry.get('summary', '')}",
                published_at=published,
                source=feed.get("name", "RSS"),
                priority=float(feed.get("priority", 1)),
            )
