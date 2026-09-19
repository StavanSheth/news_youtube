"""System health checks for persistence directories, configurations, and connectivity."""

from __future__ import annotations

import os
from typing import Any

from ..persistence import PersistencePaths


def check_system_health(
    paths: PersistencePaths,
    config: dict[str, Any] | None = None,
    check_api_keys: bool = False,
) -> dict[str, Any]:
    """Perform health checks across storage, directories, and optional API key presence."""
    status = "HEALTHY"
    checks: dict[str, Any] = {}

    # Check persistence directories
    dir_checks = {}
    for name in ("data", "output", "archive", "raw", "normalized", "rag", "state", "runs"):
        target_dir = paths.logical_dir(name) if name in {"raw", "normalized", "rag", "state", "runs"} else getattr(paths, name)
        exists = target_dir.is_dir()
        dir_checks[name] = {"path": str(target_dir), "exists": exists}
        if not exists:
            status = "DEGRADED"

    checks["directories"] = dir_checks

    # Check API keys if requested
    if check_api_keys:
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        has_key = bool(gemini_key.strip())
        checks["api_keys"] = {"gemini": "CONFIGURED" if has_key else "MISSING"}
        if not has_key:
            status = "DEGRADED"

    return {
        "status": status,
        "checks": checks,
    }


def check_source_health(
    repository: Any,
) -> dict[str, Any]:
    """Check source health records from persistence and summarize readiness."""
    all_health = {}
    try:
        all_health = repository.get_all_source_health()
    except Exception:
        return {"status": "UNKNOWN", "source_count": 0, "ready": 0, "quarantined": 0, "disabled": 0}

    ready = sum(1 for h in all_health.values() if h.get("status") == "READY")
    quarantined = sum(1 for h in all_health.values() if h.get("status") in ("QUARANTINED", "QUARANTINE"))
    disabled = sum(1 for h in all_health.values() if h.get("status") in ("DISABLED", "DISABLE"))

    status = "HEALTHY" if ready > 0 else ("DEGRADED" if quarantined > 0 else "UNKNOWN")

    return {
        "status": status,
        "source_count": len(all_health),
        "ready": ready,
        "quarantined": quarantined,
        "disabled": disabled,
        "sources": {sid: h.get("status", "UNKNOWN") for sid, h in all_health.items()},
    }
