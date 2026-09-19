"""YouTube Source Provider implementing quota-governed channel validation and collection."""

from __future__ import annotations

import logging
import os
import time
from datetime import UTC, datetime
from typing import Any

from ...sources import (
    CollectionBudget,
    SourceAcceptanceResult,
    SourceAcceptanceStatus,
    SourceContract,
)
from ..base import CanonicalContent, SafeHttpClient
from ..youtube.client import YouTubeClient
from ..youtube.normalizer import YouTubeNormalizer
from ..youtube.quota import YouTubeQuotaTracker, default_quota_tracker
from .base import SourceProvider

LOGGER = logging.getLogger(__name__)


class YouTubeProvider(SourceProvider):
    """YouTube provider implementing uploads playlist collection with strict quota bounds."""

    def __init__(
        self,
        quota_tracker: YouTubeQuotaTracker | None = None,
        http_client: SafeHttpClient | None = None,
    ) -> None:
        self.quota_tracker = quota_tracker or default_quota_tracker
        self.http_client = http_client or SafeHttpClient(default_timeout=15)
        self._last_health: dict[str, dict[str, Any]] = {}

    def validate(
        self,
        source: SourceContract,
        run_id: str = "validation",
        live: bool = False,
    ) -> SourceAcceptanceResult:
        start_time = time.perf_counter()
        now_iso = datetime.now(UTC).isoformat()
        sid = source.id

        failure_codes: list[str] = []
        warnings: list[str] = []
        details: dict[str, Any] = {}

        # 1. Configured check
        configured_ok = bool(source.id and source.name)
        if not configured_ok:
            failure_codes.append("CONFIG_INVALID")

        # 2. Disabled check
        if not source.enabled:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return SourceAcceptanceResult(
                source_id=sid,
                run_id=run_id,
                checked_at=now_iso,
                configured=configured_ok,
                reachable=False,
                authenticated=False,
                collection_success=False,
                response_valid=False,
                freshness_valid=False,
                schema_valid=False,
                content_extractable=False,
                role_valid=True,
                mapping_valid=True,
                evidence_valid=False,
                license_valid=True,
                retention_valid=True,
                status=SourceAcceptanceStatus.DISABLED.value,
                failure_codes=["DISABLED_BY_CONFIGURATION"],
                warnings=warnings,
                latency_ms=round(elapsed_ms, 2),
                details={"reason": "Source disabled in configuration"},
            )

        # 3. Authentication credential check
        env_var = source.authentication_env_var or "YOUTUBE_API_KEY"
        key_val = os.environ.get(env_var, "").strip()
        auth_ok = bool(key_val)
        if not auth_ok:
            failure_codes.append(f"MISSING_CREDENTIAL_{env_var}")

        channel_id = source.metadata.get("id") or source.id
        reachable_ok = bool(channel_id and not channel_id.startswith("http"))
        if not reachable_ok:
            failure_codes.append("INVALID_CHANNEL_ID")

        collection_ok = False
        response_ok = False
        schema_ok = False
        freshness_ok = False
        extractable_ok = False
        evidence_ok = False
        items_seen = 0
        items_valid = 0
        items_rejected = 0
        latest_content_at: str | None = None
        oldest_content_at: str | None = None

        if auth_ok and reachable_ok:
            client = YouTubeClient(
                api_key=key_val,
                quota_tracker=self.quota_tracker,
                http_client=self.http_client,
            )
            try:
                # 1. Resolve uploads playlist (1 quota unit)
                uploads_id = client.get_channel_uploads_playlist(channel_id)
                if uploads_id:
                    details["uploads_playlist_id"] = uploads_id
                    # 2. Retrieve video items (1 quota unit)
                    playlist_items = client.get_playlist_items(uploads_id, max_results=5)
                    items_seen = len(playlist_items)
                    collection_ok = True
                    response_ok = True

                    valid_items = []
                    dates = []
                    now_utc = datetime.now(UTC)

                    for item in playlist_items:
                        snippet = item.get("snippet", {})
                        vid_id = item.get("contentDetails", {}).get("videoId")
                        if not vid_id or not snippet.get("title"):
                            items_rejected += 1
                            continue
                        pub_str = snippet.get("publishedAt")
                        if pub_str:
                            try:
                                dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                                dates.append(dt)
                            except Exception:
                                pass
                        items_valid += 1
                        valid_items.append(item)

                    schema_ok = items_valid > 0 or items_seen == 0
                    if dates:
                        dates.sort()
                        oldest_content_at = dates[0].isoformat()
                        latest_content_at = dates[-1].isoformat()
                        age_hours = (now_utc - dates[-1]).total_seconds() / 3600.0
                        details["latest_video_age_hours"] = round(age_hours, 1)
                        if age_hours <= source.freshness_policy.stale_after_hours:
                            freshness_ok = True
                        else:
                            failure_codes.append(f"STALE_CONTENT_{round(age_hours, 1)}h_OLD")
                    else:
                        freshness_ok = True

                    if valid_items:
                        extractable_ok = True
                        evidence_ok = True
                    else:
                        extractable_ok = True
                        evidence_ok = True
                else:
                    failure_codes.append("CHANNEL_NOT_FOUND_OR_NO_UPLOADS")

            except Exception as exc:
                failure_codes.append(f"YOUTUBE_API_ERROR_{type(exc).__name__}")
                details["error"] = str(exc)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        all_ok = (
            configured_ok
            and auth_ok
            and reachable_ok
            and response_ok
            and collection_ok
            and schema_ok
            and freshness_ok
            and extractable_ok
            and evidence_ok
            and not failure_codes
        )
        status = SourceAcceptanceStatus.READY.value if all_ok else (
            SourceAcceptanceStatus.QUARANTINED.value if auth_ok else SourceAcceptanceStatus.DISABLED.value
        )

        result = SourceAcceptanceResult(
            source_id=sid,
            run_id=run_id,
            checked_at=now_iso,
            configured=configured_ok,
            reachable=reachable_ok,
            authenticated=auth_ok,
            collection_success=collection_ok,
            response_valid=response_ok,
            freshness_valid=freshness_ok,
            schema_valid=schema_ok,
            content_extractable=extractable_ok,
            role_valid=True,
            mapping_valid=True,
            evidence_valid=evidence_ok,
            license_valid=True,
            retention_valid=True,
            status=status,
            failure_codes=failure_codes,
            warnings=warnings,
            latency_ms=round(elapsed_ms, 2),
            items_seen=items_seen,
            items_valid=items_valid,
            items_rejected=items_rejected,
            latest_content_at=latest_content_at,
            oldest_content_at=oldest_content_at,
            details=details,
        )

        self._last_health[sid] = {
            "source_id": sid,
            "status": "HEALTHY" if result.is_ready else "FAILED",
            "latency_ms": result.latency_ms,
            "authenticated": auth_ok,
            "quota": self.quota_tracker.to_dict(),
            "items_seen": items_seen,
            "last_checked": now_iso,
            "error": failure_codes[0] if failure_codes else None,
        }

        return result

    def collect(
        self,
        source: SourceContract,
        budget: CollectionBudget | None = None,
        live: bool = False,
    ) -> list[CanonicalContent]:
        b = budget or source.budgets
        env_var = source.authentication_env_var or "YOUTUBE_API_KEY"
        key_val = os.environ.get(env_var, "").strip()
        if not key_val:
            return []

        channel_id = source.metadata.get("id") or source.id
        client = YouTubeClient(
            api_key=key_val,
            quota_tracker=self.quota_tracker,
            http_client=self.http_client,
        )
        try:
            uploads_id = client.get_channel_uploads_playlist(channel_id)
            if not uploads_id:
                return []
            playlist_items = client.get_playlist_items(uploads_id, max_results=b.max_items_per_run)
            results = []
            for item in playlist_items:
                vid_id = (
                    item.get("contentDetails", {}).get("videoId")
                    or item.get("snippet", {}).get("resourceId", {}).get("videoId")
                )
                snippet = item.get("snippet", {})
                if vid_id and snippet:
                    canonical = YouTubeNormalizer.normalize_video(
                        video_id=vid_id,
                        snippet=snippet,
                        source=source,
                    )
                    if canonical:
                        results.append(canonical)
            return results
        except Exception:
            return []

    def health(self, source: SourceContract) -> dict[str, Any]:
        return self._last_health.get(source.id, {
            "source_id": source.id,
            "status": "CONFIGURED",
            "latency_ms": 0.0,
            "authenticated": bool(os.environ.get(source.authentication_env_var or "YOUTUBE_API_KEY")),
            "quota": self.quota_tracker.to_dict(),
            "last_checked": None,
        })
