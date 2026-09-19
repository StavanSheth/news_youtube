"""RSS Source Provider implementing validation, collection, and normalization."""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import UTC, datetime
from typing import Any, Callable

import feedparser
import requests

from ...sources import (
    CollectionBudget,
    SourceAcceptanceResult,
    SourceAcceptanceStatus,
    SourceContract,
)
from ..base import CanonicalContent
from ..rss.normalizer import RssNormalizer, clean_html
from ..rss.parser import RssParser
from .base import SourceProvider

LOGGER = logging.getLogger(__name__)


class RSSProvider(SourceProvider):
    """RSS / Atom feed provider implementing acceptance, bounded collection, and health."""

    def __init__(
        self,
        timeout: int = 15,
        custom_parser: Callable[[str], Any] | None = None,
    ) -> None:
        self.timeout = timeout
        self.custom_parser = custom_parser
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
                authenticated=True,
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

        # 3. Authentication check
        auth_ok = True
        if source.authentication_required:
            env_var = source.authentication_env_var or "API_KEY"
            key_val = os.environ.get(env_var, "").strip()
            if not key_val:
                auth_ok = False
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

        req_module = getattr(sys.modules.get("intelligence.source_validation"), "requests", requests)
        req_get = getattr(req_module, "get", requests.get)

        if reachable_ok and auth_ok:
            try:
                if self.custom_parser:
                    parsed = self.custom_parser(url)
                else:
                    resp = req_get(
                        url,
                        timeout=self.timeout,
                        headers={"User-Agent": "news-youtube-intelligence/1.0"},
                    )
                    resp.raise_for_status()
                    parsed = feedparser.parse(resp.content)

                http_status = getattr(parsed, "status", 200)
                details["http_status"] = http_status
                response_ok = (http_status in {200, 301, 302}) or (not getattr(parsed, "bozo", False))

                is_valid, feed_reason, entries = RssParser.validate_feed(parsed)
                collection_ok = is_valid
                details["feed_status"] = feed_reason

                items_seen = len(entries)
                valid_entries = []
                now_utc = datetime.now(UTC)
                dates: list[datetime] = []

                for entry in entries:
                    link = entry.get("link", "")
                    title = entry.get("title", "")
                    if not link or not title:
                        items_rejected += 1
                        continue

                    pub_parsed = getattr(entry, "published_parsed", None) or entry.get("published_parsed")
                    if pub_parsed and len(pub_parsed) >= 6:
                        try:
                            dt = datetime(*pub_parsed[:6], tzinfo=UTC)
                            dates.append(dt)
                        except (ValueError, TypeError):
                            pass

                    items_valid += 1
                    valid_entries.append(entry)

                schema_ok = (items_valid > 0) or (items_seen == 0 and not getattr(parsed, "bozo", False))

                if dates:
                    dates.sort()
                    oldest_dt = dates[0]
                    latest_dt = dates[-1]
                    oldest_content_at = oldest_dt.isoformat()
                    latest_content_at = latest_dt.isoformat()

                    age_hours = (now_utc - latest_dt).total_seconds() / 3600.0
                    details["latest_item_age_hours"] = round(age_hours, 1)

                    if age_hours <= source.freshness_policy.stale_after_hours:
                        freshness_ok = True
                    else:
                        failure_codes.append(f"STALE_CONTENT_{round(age_hours, 1)}h_OLD")
                elif items_valid > 0:
                    warnings.append("NO_PARSEABLE_PUBLICATION_DATES")
                    freshness_ok = True
                else:
                    freshness_ok = True

                if valid_entries:
                    first_entry = valid_entries[0]
                    summary_text = clean_html(str(first_entry.get("summary", "") or first_entry.get("title", "")))
                    extractable_ok = len(summary_text) > 0
                    evidence_ok = len(summary_text) > 0
                else:
                    extractable_ok = True
                    evidence_ok = True

            except Exception as exc:
                failure_codes.append(f"NETWORK_ERROR_{type(exc).__name__}")
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
        status = SourceAcceptanceStatus.READY.value if all_ok else SourceAcceptanceStatus.QUARANTINED.value

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
        max_items = b.max_items_per_run
        url = source.url

        if not url:
            return []

        try:
            if self.custom_parser:
                parsed = self.custom_parser(url)
            else:
                resp = requests.get(url, timeout=b.timeout_seconds, headers={"User-Agent": "news-youtube-intelligence/1.0"})
                resp.raise_for_status()
                parsed = feedparser.parse(resp.content)

            entries = getattr(parsed, "entries", []) or []
            selected_entries = entries[:max_items]

            results = []
            for entry in selected_entries:
                item = RssNormalizer.normalize_entry(entry, source)
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
            "last_checked": None,
        })
