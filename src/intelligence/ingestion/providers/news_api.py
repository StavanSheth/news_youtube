"""News API Source Provider implementing authentication, bounded pagination, and health."""

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
from ..news_api.client import NewsApiClient
from ..news_api.normalizer import NewsApiNormalizer
from .base import SourceProvider

LOGGER = logging.getLogger(__name__)


class NewsAPIProvider(SourceProvider):
    """News API provider implementing acceptance, bounded collection, and quota tracking."""

    def __init__(
        self,
        http_client: SafeHttpClient | None = None,
    ) -> None:
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
        configured_ok = bool(source.id and source.name and source.url)
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
        env_var = source.authentication_env_var or "NEWS_API_KEY"
        key_val = os.environ.get(env_var, "").strip()
        auth_ok = bool(key_val)
        if not auth_ok:
            failure_codes.append(f"MISSING_CREDENTIAL_{env_var}")

        # 4. URL check
        url = source.url
        reachable_ok = url.startswith("http://") or url.startswith("https://")
        if not reachable_ok:
            failure_codes.append("INVALID_URL")

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
            client = NewsApiClient(
                api_key_env=env_var,
                http_client=self.http_client,
                source_id=sid,
            )
            try:
                # Fetch up to 5 items to validate schema
                articles = client.fetch_articles(
                    endpoint_url=url,
                    params={"q": "news"},
                    max_pages=1,
                    max_items=5,
                )
                items_seen = len(articles)
                collection_ok = True
                response_ok = True

                valid_articles = []
                dates = []
                now_utc = datetime.now(UTC)

                for art in articles:
                    title = art.get("title")
                    art_url = art.get("url")
                    if not title or not art_url:
                        items_rejected += 1
                        continue
                    pub_str = art.get("publishedAt") or art.get("published_at")
                    if pub_str:
                        try:
                            dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                            dates.append(dt)
                        except Exception:
                            pass
                    items_valid += 1
                    valid_articles.append(art)

                schema_ok = items_valid > 0 or items_seen == 0
                if dates:
                    dates.sort()
                    oldest_content_at = dates[0].isoformat()
                    latest_content_at = dates[-1].isoformat()
                    age_hours = (now_utc - dates[-1]).total_seconds() / 3600.0
                    details["latest_item_age_hours"] = round(age_hours, 1)
                    if age_hours <= source.freshness_policy.stale_after_hours:
                        freshness_ok = True
                    else:
                        failure_codes.append(f"STALE_CONTENT_{round(age_hours, 1)}h_OLD")
                else:
                    freshness_ok = True

                if valid_articles:
                    desc = valid_articles[0].get("description") or valid_articles[0].get("content") or ""
                    extractable_ok = len(desc) > 0
                    evidence_ok = len(desc) > 0
                else:
                    extractable_ok = True
                    evidence_ok = True

            except Exception as exc:
                failure_codes.append(f"NEWS_API_ERROR_{type(exc).__name__}")
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
        env_var = source.authentication_env_var or "NEWS_API_KEY"
        key_val = os.environ.get(env_var, "").strip()
        if not key_val:
            return []

        client = NewsApiClient(
            api_key_env=env_var,
            http_client=self.http_client,
            source_id=source.id,
        )
        try:
            articles = client.fetch_articles(
                endpoint_url=source.url,
                max_pages=b.max_pages,
                max_items=b.max_items_per_run,
            )
            results = []
            for art in articles:
                item = NewsApiNormalizer.normalize_article(art, source)
                if item:
                    results.append(item)
            return results
        except Exception:
            return []

    def health(self, source: SourceContract) -> dict[str, Any]:
        return self._last_health.get(source.id, {
            "source_id": source.id,
            "status": "CONFIGURED",
            "latency_ms": 0.0,
            "authenticated": bool(os.environ.get(source.authentication_env_var or "NEWS_API_KEY")),
            "last_checked": None,
        })
