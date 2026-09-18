"""Business rules validation for actions, opportunities, publication cutoffs, and no-update integrity."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

VALID_ACTION_TYPES = {
    "SOURCE_STATED",
    "AI_DERIVED",
    "AI_DERIVED_EXPERIMENT",
    "PERSONALIZED_APPLICATION",
}

VALID_OPPORTUNITY_STATUSES = {
    "VERIFIED",
    "PARTIALLY_VERIFIED",
    "UNVERIFIED",
    "EXPIRED",
}


def _parse_utc_datetime(val: Any) -> datetime | None:
    if isinstance(val, datetime):
        return val.astimezone(UTC) if val.tzinfo else val.replace(tzinfo=UTC)
    if isinstance(val, str) and val.strip():
        try:
            parsed = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except (ValueError, TypeError):
            return None
    return None


def validate_business_rules(
    analysis: dict[str, Any],
    *,
    publication_cutoff: datetime | str | None = None,
    channel_restrictions: list[str] | set[str] | None = None,
) -> tuple[bool, list[str]]:
    """Validate business rules for actionable insights, opportunities, publication cutoffs, and integrity."""
    errors = []
    if not analysis:
        return False, ["Analysis payload is empty"]

    # Check actionable insights attribution
    actions = analysis.get("actions", [])
    if isinstance(actions, list):
        for action in actions:
            if isinstance(action, dict):
                action_type = str(action.get("action_type", "AI_DERIVED")).upper()
                if action_type not in VALID_ACTION_TYPES:
                    errors.append(f"Invalid action_type: '{action_type}'; must be one of {sorted(VALID_ACTION_TYPES)}")

    # Check opportunity structure if present
    opportunities = analysis.get("opportunities", [])
    if isinstance(opportunities, list):
        for opp in opportunities:
            if isinstance(opp, dict):
                status = str(opp.get("status", "UNVERIFIED")).upper()
                if status not in VALID_OPPORTUNITY_STATUSES:
                    errors.append(f"Invalid opportunity status: '{status}'; must be one of {sorted(VALID_OPPORTUNITY_STATUSES)}")
                if opp.get("status") == "VERIFIED" and not opp.get("application_url"):
                    errors.append("VERIFIED opportunity must have a valid application_url")

    # Enforce no-update integrity: technical errors must NEVER convert to NO_MAJOR_UPDATE
    analysis_status = str(analysis.get("status", "")).upper()
    if analysis_status in {"NO_MAJOR_UPDATE", "CHECKED_NO_MAJOR_UPDATE"}:
        if analysis.get("error") or analysis.get("error_type") or analysis.get("technical_error"):
            errors.append("Technical errors must NEVER convert to NO_MAJOR_UPDATE")
        if analysis.get("rag_error") or analysis.get("provider_error"):
            errors.append("Provider or retrieval failure must not produce NO_MAJOR_UPDATE")

    # Future data and publication cutoff rejection
    cutoff_dt = _parse_utc_datetime(publication_cutoff)
    evidence_list = analysis.get("evidence", [])
    if isinstance(evidence_list, list):
        for entry in evidence_list:
            if isinstance(entry, dict):
                published_raw = (
                    entry.get("published_at")
                    or entry.get("metadata", {}).get("published_at")
                )
                if published_raw:
                    published_dt = _parse_utc_datetime(published_raw)
                    if published_dt:
                        if cutoff_dt and published_dt > cutoff_dt:
                            errors.append(
                                f"Evidence timestamp {published_raw} exceeds publication cutoff {cutoff_dt.isoformat()}"
                            )

    # Channel restrictions
    if channel_restrictions:
        allowed_channels = {c.lower() for c in channel_restrictions}
        if isinstance(evidence_list, list):
            for entry in evidence_list:
                if isinstance(entry, dict):
                    kind = str(entry.get("kind") or entry.get("metadata", {}).get("kind", "")).lower()
                    if kind and kind not in allowed_channels:
                        errors.append(f"Evidence channel '{kind}' not permitted by channel restrictions: {sorted(allowed_channels)}")

    return len(errors) == 0, errors
