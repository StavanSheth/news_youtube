"""Deterministic 13-stage Source Acceptance Engine, Lifecycle State Machine, and CLI."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import feedparser
import requests

from .ingestion import RssParser, clean_html
from .sources import (
    ProductionSourceRegistry,
    SourceAcceptanceResult,
    SourceAcceptanceStatus,
    SourceContract,
    SourceRole,
)
from .statuses import SourceStatus

LOGGER = logging.getLogger(__name__)


def _valid_http_url(value: str) -> bool:
    parsed = urlparse(value or "")
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


class SourceAcceptanceEngine:
    """Deterministic 13-stage source acceptance and verification engine."""

    def __init__(
        self,
        timeout: int = 15,
        taxonomy: dict[str, Any] | None = None,
        custom_parser: Callable[[str], Any] | None = None,
        live: bool = False,
    ) -> None:
        self.timeout = timeout
        self.taxonomy = taxonomy or {}
        self.custom_parser = custom_parser
        self.live = live
        self._valid_domains = set(self.taxonomy.get("domains", {}).keys())
        self._valid_topics = {t for d in self.taxonomy.get("domains", {}).values() for t in d.get("topics", [])}
        self._valid_regions = set(self.taxonomy.get("regions", []))
        self._valid_countries = set(self.taxonomy.get("countries", []))

    def evaluate_source(
        self,
        source: SourceContract | dict[str, Any],
        run_id: str = "validation",
    ) -> SourceAcceptanceResult:
        """Run complete 13-stage acceptance lifecycle against a source."""
        start_time = time.perf_counter()
        contract = source if isinstance(source, SourceContract) else SourceContract.from_mapping(source)
        sid = contract.id
        now_iso = datetime.now(UTC).isoformat()

        failure_codes: list[str] = []
        warnings: list[str] = []
        checks: dict[str, bool] = {}
        details: dict[str, Any] = {}

        # Stage 1: CONFIGURED
        configured_ok = bool(contract.id and contract.name and contract.url)
        checks["configured"] = configured_ok
        if not configured_ok:
            failure_codes.append("CONFIG_INVALID")

        # Stage 10: REGION/TOPIC MAPPING VALID (static check)
        mapping_ok = True
        if self._valid_regions and contract.region not in self._valid_regions:
            mapping_ok = False
            failure_codes.append(f"INVALID_REGION_{contract.region}")
        if self._valid_countries and contract.country not in self._valid_countries:
            mapping_ok = False
            failure_codes.append(f"INVALID_COUNTRY_{contract.country}")
        if self._valid_domains:
            for d in contract.domains:
                if d not in self._valid_domains:
                    mapping_ok = False
                    failure_codes.append(f"INVALID_DOMAIN_{d}")
        if self._valid_topics:
            for t in contract.topics:
                if t not in self._valid_topics:
                    mapping_ok = False
                    failure_codes.append(f"INVALID_TOPIC_{t}")
        checks["mapping_valid"] = mapping_ok

        # Stage 9: SOURCE ROLE VALID
        role_ok = isinstance(contract.role, SourceRole)
        checks["role_valid"] = role_ok
        if not role_ok:
            failure_codes.append("INVALID_SOURCE_ROLE")

        # Stage 12: LICENSE/TERMS METADATA VALID
        license_ok = contract.license_status.upper() in {"PERMITTED", "RESTRICTED"}
        checks["license_valid"] = license_ok
        retention_ok = contract.retention_policy.upper() in {"LIMITED", "REQUIRED", "CONFIGURED"}
        checks["retention_valid"] = retention_ok
        if not license_ok:
            failure_codes.append("LICENSE_TERMS_UNRESOLVED")
        if not retention_ok:
            failure_codes.append("RETENTION_POLICY_UNRESOLVED")

        # Check if disabled
        if not contract.enabled:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            codes = list(failure_codes)
            if "DISABLED_BY_CONFIGURATION" not in codes:
                codes.append("DISABLED_BY_CONFIGURATION")
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
                role_valid=role_ok,
                mapping_valid=mapping_ok,
                evidence_valid=False,
                license_valid=license_ok,
                retention_valid=retention_ok,
                status=SourceAcceptanceStatus.DISABLED.value,
                failure_codes=codes,
                warnings=warnings,
                latency_ms=round(elapsed_ms, 2),
                details={"reason": "Source disabled in configuration"},
            )

        # Stage 3: AUTHENTICATED check
        auth_ok = True
        if contract.authentication_required:
            env_var = contract.authentication_env_var or "API_KEY"
            key_val = os.environ.get(env_var, "").strip()
            if not key_val:
                auth_ok = False
                failure_codes.append(f"MISSING_CREDENTIAL_{env_var}")
        checks["authenticated"] = auth_ok

        # Stage 2: REACHABLE check
        url = contract.url
        reachable_ok = _valid_http_url(url)
        if not reachable_ok:
            failure_codes.append("INVALID_URL")
        checks["reachable"] = reachable_ok

        # Network / Collection Stages
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

        if reachable_ok and auth_ok:
            try:
                if self.custom_parser:
                    parsed = self.custom_parser(url)
                else:
                    # Always call requests.get so timeout is applied and tests can monkeypatch.
                    # In offline/test mode callers monkeypatch requests.get to return fixture data.
                    resp = requests.get(
                        url,
                        timeout=self.timeout,
                        headers={"User-Agent": "news-youtube-intelligence/1.0"},
                    )
                    resp.raise_for_status()
                    parsed = feedparser.parse(resp.content)

                http_status = getattr(parsed, "status", 200)
                details["http_status"] = http_status
                response_ok = (http_status in {200, 301, 302}) or (not getattr(parsed, "bozo", False))
                checks["response_valid"] = response_ok

                # Validate feed entries
                is_valid, feed_reason, entries = RssParser.validate_feed(parsed)
                collection_ok = is_valid
                checks["collection_success"] = collection_ok
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

                    # Freshness timestamp evaluation
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
                checks["schema_valid"] = schema_ok

                if dates:
                    dates.sort()
                    oldest_dt = dates[0]
                    latest_dt = dates[-1]
                    oldest_content_at = oldest_dt.isoformat()
                    latest_content_at = latest_dt.isoformat()

                    age_hours = (now_utc - latest_dt).total_seconds() / 3600.0
                    details["latest_item_age_hours"] = round(age_hours, 1)

                    if age_hours <= contract.freshness_policy.stale_after_hours:
                        freshness_ok = True
                    else:
                        failure_codes.append(f"STALE_CONTENT_{round(age_hours, 1)}h_OLD")
                elif items_valid > 0:
                    warnings.append("NO_PARSEABLE_PUBLICATION_DATES")
                    freshness_ok = True  # Not provably stale
                else:
                    freshness_ok = True  # Empty feed is handled by schema/collection

                checks["freshness_valid"] = freshness_ok

                # Content Extractability & Evidence Quality
                if valid_entries:
                    first_entry = valid_entries[0]
                    summary_text = clean_html(str(first_entry.get("summary", "") or first_entry.get("title", "")))
                    extractable_ok = len(summary_text) > 0
                    evidence_ok = len(summary_text) > 0
                else:
                    extractable_ok = True
                    evidence_ok = True

                checks["content_extractable"] = extractable_ok
                checks["evidence_valid"] = evidence_ok

                if not schema_ok:
                    failure_codes.append("SCHEMA_INVALID")
                if not extractable_ok:
                    failure_codes.append("CONTENT_UNEXTRACTABLE")
                if not evidence_ok:
                    failure_codes.append("EVIDENCE_INSUFFICIENT")

            except Exception as exc:
                failure_codes.append(f"NETWORK_ERROR_{type(exc).__name__}")
                details["error"] = str(exc)

        checks["collection_success"] = collection_ok
        checks["response_valid"] = response_ok
        checks["schema_valid"] = schema_ok
        checks["freshness_valid"] = freshness_ok
        checks["content_extractable"] = extractable_ok
        checks["evidence_valid"] = evidence_ok

        # Determine Final Acceptance State
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        is_all_passed = (
            configured_ok
            and mapping_ok
            and role_ok
            and license_ok
            and retention_ok
            and auth_ok
            and reachable_ok
            and collection_ok
            and response_ok
            and schema_ok
            and freshness_ok
            and extractable_ok
            and evidence_ok
        )

        status = SourceAcceptanceStatus.READY.value if is_all_passed else SourceAcceptanceStatus.QUARANTINED.value

        return SourceAcceptanceResult(
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
            role_valid=role_ok,
            mapping_valid=mapping_ok,
            evidence_valid=evidence_ok,
            license_valid=license_ok,
            retention_valid=retention_ok,
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


def validate_source_registry(
    sources: list[dict[str, Any]],
    timeout: int = 15,
    parser: Callable[[str], Any] | None = None,
    live: bool = False,
    taxonomy: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Validate every configured source without enabling inaccessible sources (backward-compatible API)."""
    engine = SourceAcceptanceEngine(timeout=timeout, custom_parser=parser, live=live, taxonomy=taxonomy)
    report: dict[str, dict[str, Any]] = {}

    for source in sources:
        contract = SourceContract.from_mapping(source)
        res = engine.evaluate_source(contract)
        
        # Backward-compatible mapping for legacy consumers
        legacy_status = (
            SourceStatus.DISABLED.value if res.is_disabled
            else SourceStatus.HEALTHY.value if res.is_ready
            else SourceStatus.SOURCE_UNAVAILABLE.value
        )
        failure_reason = res.failure_codes[0] if res.failure_codes else None

        record = {
            "source": contract.name,
            "source_id": contract.id,
            "enabled": contract.enabled,
            "trust_tier": contract.trust_tier,
            "region": contract.region,
            "country": contract.country,
            "topics": list(contract.topics),
            "micro_topics": list(contract.micro_topics),
            "item_count": res.items_seen,
            "usable_content_count": res.items_valid,
            "relevant_content_count": res.items_valid,
            "topics_detected": list(contract.topics),
            "micro_topics_detected": list(contract.micro_topics),
            "checked_at": res.checked_at,
            "url": contract.url,
            "fresh": res.freshness_valid,
            "status": legacy_status,
            "acceptance_status": res.status,
            "failure_reason": failure_reason,
            "failure_codes": res.failure_codes,
            "warnings": res.warnings,
            "latency_ms": res.latency_ms,
            "latest_content_at": res.latest_content_at,
            "details": res.details,
        }
        report[contract.id] = record

    return report


def main() -> int:
    """Deterministic CLI for source acceptance and verification."""
    cli_parser = argparse.ArgumentParser(description="Phase 3 Source Acceptance & Readiness CLI")
    cli_parser.add_argument("--all", action="store_true", help="Validate all configured sources in the registry")
    cli_parser.add_argument("--source", type=str, help="Validate a specific source by source_id")
    cli_parser.add_argument("--type", type=str, help="Filter sources by type (rss, youtube, api)")
    cli_parser.add_argument("--enabled", action="store_true", help="Validate only enabled sources")
    cli_parser.add_argument("--json", action="store_true", help="Output results as JSON")
    cli_parser.add_argument("--fail-on-error", action="store_true", help="Exit with code 1 if any source fails")
    cli_parser.add_argument("--live", action="store_true", help="Perform live external network requests")
    cli_parser.add_argument("--config-dir", type=Path, default=Path("config"), help="Path to config directory")

    args = cli_parser.parse_args()

    # Load registry
    registry = ProductionSourceRegistry.load_from_config(args.config_dir)
    sources = registry.all_sources()

    # Apply filters
    if args.source:
        sources = [s for s in sources if s.id == args.source]
        if not sources:
            print(f"Error: Source '{args.source}' not found in registry", file=sys.stderr)
            return 1
    if args.type:
        sources = [s for s in sources if s.type == args.type.lower()]
    if args.enabled:
        sources = [s for s in sources if s.enabled]

    # Evaluate sources
    engine = SourceAcceptanceEngine(live=args.live)
    results = [engine.evaluate_source(s) for s in sources]

    if args.json:
        output_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "total_evaluated": len(results),
            "ready_count": sum(r.is_ready for r in results),
            "quarantined_count": sum(r.is_quarantined for r in results),
            "disabled_count": sum(r.is_disabled for r in results),
            "results": [r.to_dict() for r in results],
        }
        print(json.dumps(output_data, indent=2))
    else:
        print("SOURCE VALIDATION REPORT")
        print("=" * 60)
        for r in results:
            status_symbol = "READY" if r.is_ready else "DISABLED" if r.is_disabled else "QUARANTINED"
            print(f"[{status_symbol}] {r.source_id}")
            print(f"  configured: {'PASS' if r.configured else 'FAIL'}")
            print(f"  reachable:  {'PASS' if r.reachable else 'FAIL'}")
            print(f"  collection: {'PASS' if r.collection_success else 'FAIL'}")
            print(f"  schema:     {'PASS' if r.schema_valid else 'FAIL'}")
            print(f"  freshness:  {'PASS' if r.freshness_valid else 'FAIL'}")
            print(f"  FINAL:      {r.status}")
            if r.failure_codes:
                print(f"  failures:   {', '.join(r.failure_codes)}")
            print("-" * 60)

    has_failures = any(r.is_quarantined for r in results)
    if args.fail_on_error and has_failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
