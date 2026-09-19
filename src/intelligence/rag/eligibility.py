"""Hard eligibility filtering for RAG candidate evidence before ranking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import re
from typing import Any

from .query import RetrievalRequest

from dataclasses import dataclass

@dataclass(frozen=True)
class TemporalEvidencePolicy:
    """Explicit policy enforcing future-data protection and timestamp integrity."""

    publication_cutoff: datetime | None = None
    now: datetime | None = None
    max_lookback_days: int = 30

    def evaluate(
        self,
        published_at: datetime | None,
        retrieved_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> tuple[bool, str]:
        now = self.now or datetime.now(UTC)
        if published_at is not None:
            if self.publication_cutoff is not None and published_at > self.publication_cutoff:
                return False, "FUTURE_EVIDENCE_EXCEEDS_CUTOFF"
            if published_at > now:
                return False, "FUTURE_EVIDENCE_AHEAD_OF_NOW"
            if retrieved_at and retrieved_at < published_at:
                return False, "RETRIEVED_PRECEDES_PUBLISHED"
        return True, "OK"



def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except (TypeError, ValueError):
        return None


def _freshness_cutoff(freshness: str, now: datetime) -> datetime | None:
    match = re.fullmatch(r"(\d+)d", str(freshness or "").strip().lower())
    if not match:
        return None
    return now - timedelta(days=int(match.group(1)))


def check_chunk_eligibility(
    chunk: dict[str, Any],
    request: RetrievalRequest | None = None,
    *,
    now: datetime | None = None,
    publication_cutoff: datetime | None = None,
    disabled_sources: set[str] | None = None,
    quarantined_sources: set[str] | None = None,
) -> tuple[bool, str]:
    """Perform pre-ranking hard eligibility verification on a candidate chunk."""
    now = now or datetime.now(UTC)
    metadata = chunk.get("metadata", {})
    text = chunk.get("text", "") or ""

    content_id = metadata.get("content_id") or chunk.get("id")
    if not content_id:
        return False, "MISSING_CONTENT_ID"

    source_id = metadata.get("source_id") or metadata.get("source")
    if not source_id:
        return False, "MISSING_SOURCE_ID"

    url = metadata.get("url") or ""
    if url and not url.startswith(("http://", "https://")):
        return False, "INVALID_URL_SCHEME"

    # Strict Quarantine check per Section 12
    if (
        metadata.get("quarantined")
        or str(metadata.get("status", "")).upper() in ("QUARANTINED", "QUARANTINE")
        or str(metadata.get("source_acceptance_status", "")).upper() in ("QUARANTINED", "QUARANTINE")
        or str(metadata.get("acceptance_status", "")).upper() in ("QUARANTINED", "QUARANTINE")
    ):
        return False, "QUARANTINED_SOURCE"

    if quarantined_sources and str(source_id).lower() in {s.lower() for s in quarantined_sources}:
        return False, "QUARANTINED_SOURCE"

    # Source enabled check
    if disabled_sources and str(source_id).lower() in {s.lower() for s in disabled_sources}:
        return False, "DISABLED_SOURCE"

    # Trust tier check (1..4)
    trust_tier = metadata.get("trust_tier")
    if trust_tier is not None:
        try:
            if not 1 <= int(trust_tier) <= 4:
                return False, "INVALID_TRUST_TIER"
        except (ValueError, TypeError):
            return False, "INVALID_TRUST_TIER"

    # Temporal / Cutoff check (Future data protection via TemporalEvidencePolicy)
    raw_published = metadata.get("published_at")
    published_at = _parse_timestamp(raw_published)
    retrieved_at = _parse_timestamp(metadata.get("retrieved_at"))
    updated_at = _parse_timestamp(metadata.get("updated_at"))
    temporal_policy = TemporalEvidencePolicy(publication_cutoff=publication_cutoff, now=now)
    temporal_ok, temporal_reason = temporal_policy.evaluate(published_at, retrieved_at, updated_at)
    if not temporal_ok:
        return False, temporal_reason

    if request is not None:
        # Freshness check
        if request.freshness and published_at is not None:
            cutoff = _freshness_cutoff(request.freshness, now)
            if cutoff and published_at < cutoff:
                return False, "FRESHNESS_EXPIRED"

        # Exclusion concepts
        text_lower = text.lower()
        all_exclusions = tuple(dict.fromkeys(tuple(request.exclusions) + tuple(request.exclusion_concepts)))
        for exclusion in all_exclusions:
            if exclusion and str(exclusion).lower() in text_lower:
                return False, f"EXCLUDED_CONCEPT:{exclusion}"

        # Micro-topic match authorization check (only if chunk has micro-topic metadata)
        if request.micro_topic_id:
            matches = metadata.get("micro_topic_matches")
            tag = metadata.get("micro_topic_id")
            if matches is not None or tag is not None:
                has_direct_match = any(
                    isinstance(m, dict) and m.get("micro_topic_id") == request.micro_topic_id
                    for m in (matches or [])
                )
                has_tag_match = tag == request.micro_topic_id
                concepts_to_check = [request.micro_topic_id, *request.required_concepts]
                has_concept_match = any(
                    c.replace("-", " ").replace("_", " ").rstrip("s").lower() in text_lower
                    for c in concepts_to_check
                    if c
                )
                if not (has_direct_match or has_tag_match or has_concept_match):
                    return False, "UNAUTHORIZED_MICRO_TOPIC"

    # Provenance requirement
    if "provenance" in metadata and metadata["provenance"] is None and url:
        return False, "INVALID_PROVENANCE"

    return True, "ELIGIBLE"


def filter_eligible_candidates(
    candidates: list[dict[str, Any]],
    request: RetrievalRequest | None = None,
    *,
    now: datetime | None = None,
    publication_cutoff: datetime | None = None,
    disabled_sources: set[str] | None = None,
    quarantined_sources: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Filter candidates, returning eligible items and full rejection diagnostics."""
    eligible = []
    rejected = []
    reasons: dict[str, int] = {}

    for chunk in candidates:
        is_eligible, reason = check_chunk_eligibility(
            chunk,
            request,
            now=now,
            publication_cutoff=publication_cutoff,
            disabled_sources=disabled_sources,
            quarantined_sources=quarantined_sources,
        )
        if is_eligible:
            eligible.append(chunk)
        else:
            rejected.append({"id": chunk.get("id", "unknown"), "reason": reason})
            reasons[reason] = reasons.get(reason, 0) + 1

    diagnostics = {
        "total_candidates": len(candidates),
        "eligible_count": len(eligible),
        "rejected_count": len(rejected),
        "rejection_reasons": reasons,
        "rejections": rejected[:20],
    }
    return eligible, diagnostics
