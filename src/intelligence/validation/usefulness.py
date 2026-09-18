"""Usefulness and genericness validation rejecting ungrounded buzzwords and filler."""

from __future__ import annotations

import re
from typing import Any

GENERIC_BUZZWORD_PATTERNS = [
    r"companies should monitor this",
    r"stakeholders should stay informed",
    r"this could have an impact",
    r"further developments should be watched",
    r"ai continues to evolve rapidly",
    r"remains to be seen",
    r"only time will tell",
    r"is a game-changer",
    r"significant for the industry",
]


def validate_usefulness(analysis: dict[str, Any]) -> tuple[bool, list[str]]:
    """Detect generic filler and verify concrete analytical mechanism."""
    warnings = []
    if not analysis:
        return False, ["Analysis payload is empty"]

    combined_text = " ".join([
        " ".join(analysis.get("facts", [])),
        " ".join(analysis.get("actionable_insights", [])),
        str(analysis.get("summary", "")),
    ]).lower()

    for pattern in GENERIC_BUZZWORD_PATTERNS:
        if re.search(pattern, combined_text):
            # Check if there is concrete mitigation (e.g. mentions specific actors or metrics)
            if not any(token in combined_text for token in ("because", "due to", "specifically", "measured", "percent", "%")):
                warnings.append(f"Analysis contains ungrounded generic phrase: '{pattern}'")

    return len(warnings) == 0, warnings
