"""Readiness checks and validation for micro-topics."""

from __future__ import annotations

from typing import Any
from ..contracts import ProductionStatus


def check_microtopic_readiness(
    entry: dict[str, Any],
    theme: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate whether a micro-topic is fully ready for production intelligence."""
    reasons = []
    profile_complete = bool(entry.get("positive_signals")) or bool(entry.get("aliases"))
    if not profile_complete:
        reasons.append("Missing signals and aliases")

    theme_pass = theme is not None and bool(theme.get("questions"))
    if not theme_pass:
        reasons.append("Missing or empty theme contract")

    retrieval_pass = bool(entry.get("retrieval_intent"))
    if not retrieval_pass:
        reasons.append("Missing retrieval intent")

    ready = profile_complete and theme_pass and retrieval_pass
    status = ProductionStatus.PRODUCTION_READY if ready else ProductionStatus.DEVELOPMENT

    return {
        "micro_topic_id": entry.get("micro_topic_id"),
        "status": status.value,
        "production_ready": ready,
        "reasons": reasons,
        "profile_complete": profile_complete,
        "theme_pass": theme_pass,
        "retrieval_contract_pass": retrieval_pass,
        "evidence_scope_pass": True,
    }
