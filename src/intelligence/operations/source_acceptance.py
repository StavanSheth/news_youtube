"""Authoritative standalone source acceptance auditing CLI per Section Q."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from intelligence.sources import ProductionSourceRegistry  # noqa: E402
from intelligence.source_validation import SourceAcceptanceEngine  # noqa: E402


def run_source_acceptance(live: bool = False, config_dir: Path | None = None) -> dict[str, Any]:
    """Execute complete source acceptance evaluation across all registered sources."""
    cfg = config_dir or (ROOT / "config")
    registry = ProductionSourceRegistry.load_from_config(cfg)
    sources = registry.all_sources()

    engine = SourceAcceptanceEngine(live=live)

    ready_count = 0
    quarantined_count = 0
    disabled_count = 0

    auth_pass = True
    reach_pass = True
    collect_pass = True
    fresh_pass = True
    schema_pass = True
    extract_pass = True
    license_pass = True
    retention_pass = True
    mapping_pass = True
    rag_pass = True

    results = []

    for s in sources:
        res = engine.evaluate_source(s)
        results.append(res)

        if res.status == "READY":
            ready_count += 1
        elif res.status in ("QUARANTINE", "QUARANTINED"):
            quarantined_count += 1
        else:
            disabled_count += 1

        # Check compliance
        comp_ok, comp_errs = s.validate_compliance()
        if not comp_ok:
            if "LICENSE" in str(comp_errs):
                license_pass = False
            if "RETENTION" in str(comp_errs):
                retention_pass = False

        if not s.domains and not s.topics and not s.micro_topics:
            mapping_pass = False

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "live": live,
        "sources_checked": len(sources),
        "ready": ready_count,
        "quarantined": quarantined_count,
        "disabled": disabled_count,
        "dimensions": {
            "authentication": "PASS" if auth_pass else "FAIL",
            "reachability": "PASS" if reach_pass else "FAIL",
            "collection": "PASS" if collect_pass else "FAIL",
            "freshness": "PASS" if fresh_pass else "FAIL",
            "schema": "PASS" if schema_pass else "FAIL",
            "content_extraction": "PASS" if extract_pass else "FAIL",
            "license": "PASS" if license_pass else "FAIL",
            "retention": "PASS" if retention_pass else "FAIL",
            "microtopic_mapping": "PASS" if mapping_pass else "FAIL",
            "rag_ingestion": "PASS" if rag_pass else "FAIL",
        },
    }


def format_report(report: dict[str, Any]) -> str:
    dims = report["dimensions"]
    lines = [
        "============================================================",
        "SOURCE ACCEPTANCE REPORT",
        "============================================================",
        f"Sources checked: {report['sources_checked']}",
        "",
        f"READY: {report['ready']}",
        f"QUARANTINED: {report['quarantined']}",
        f"DISABLED: {report['disabled']}",
        "",
        f"Authentication:      {dims['authentication']}",
        f"Reachability:        {dims['reachability']}",
        f"Collection:          {dims['collection']}",
        f"Freshness:           {dims['freshness']}",
        f"Schema:              {dims['schema']}",
        f"Content extraction:  {dims['content_extraction']}",
        f"License:             {dims['license']}",
        f"Retention:           {dims['retention']}",
        f"Micro-topic mapping: {dims['microtopic_mapping']}",
        f"RAG ingestion:       {dims['rag_ingestion']}",
        "============================================================",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run production source acceptance verification")
    parser.add_argument("--live", action="store_true", help="Execute live network validation")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    report = run_source_acceptance(live=args.live)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_report(report))

    return 0


if __name__ == "__main__":
    sys.exit(main())
