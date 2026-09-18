"""Business rules validation for actions, opportunities, and score calibrations."""

from __future__ import annotations

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


def validate_business_rules(analysis: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate business rules for actionable insights, opportunities, and scores."""
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

    return len(errors) == 0, errors
