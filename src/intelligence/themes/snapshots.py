"""Theme snapshot persistence and reproducibility contract."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def compute_theme_fingerprint(theme: dict[str, Any]) -> str:
    """Deterministic hash of theme analytical configuration."""
    stable_keys = (
        "id",
        "theme_id",
        "version",
        "questions",
        "evidence",
        "evidence_requirements",
        "significance_rules",
        "stream_rules",
        "output",
        "output_requirements",
        "no_update_policy",
        "analysis_contract",
        "retrieval_intent",
    )
    payload = {
        key: theme.get(key)
        for key in stable_keys
        if theme.get(key) not in (None, "", [], {})
    }
    dumped = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()[:16]


def create_theme_snapshot(
    theme: dict[str, Any],
    micro_topic_id: str | None = None,
    resolution_level: str | None = None,
) -> dict[str, Any]:
    """Create a persistent snapshot record for intelligence results."""
    resolved = resolution_level or theme.get("resolution_level", "exact_micro_topic")
    version = str(theme.get("version", "1.0.0"))
    theme_id = str(theme.get("id") or theme.get("theme_id", "domain-fallback"))
    mt_id = micro_topic_id or theme.get("micro_topic_id") or theme.get("micro_topic")

    return {
        "theme_id": theme_id,
        "theme_version": version,
        "micro_topic_id": mt_id,
        "resolution_level": resolved,
        "theme_fingerprint": compute_theme_fingerprint(theme),
        "snapshot_timestamp": datetime.now(timezone.utc).isoformat(),
    }


def verify_theme_snapshot(
    snapshot: dict[str, Any],
    theme: dict[str, Any],
) -> tuple[bool, str | None]:
    """Verify whether a theme has changed since a snapshot was generated."""
    expected_id = snapshot.get("theme_id")
    current_id = theme.get("id") or theme.get("theme_id")
    if expected_id != current_id:
        return False, f"Theme ID mismatch: expected {expected_id}, got {current_id}"

    expected_version = snapshot.get("theme_version")
    current_version = str(theme.get("version", "1.0.0"))
    if expected_version != current_version:
        return False, f"Theme version mismatch: expected {expected_version}, got {current_version}"

    expected_fingerprint = snapshot.get("theme_fingerprint")
    current_fingerprint = compute_theme_fingerprint(theme)
    if expected_fingerprint and expected_fingerprint != current_fingerprint:
        return False, f"Theme fingerprint mismatch: expected {expected_fingerprint}, got {current_fingerprint}"

    return True, None
