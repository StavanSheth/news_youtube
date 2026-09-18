"""Edition lifecycle and context resolution."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from ..contracts import EditionContext, EditionType, RunContext, build_edition_context


def resolve_edition_context(
    settings: dict[str, Any],
    started_at: datetime,
    versions: Any,
) -> tuple[EditionContext, RunContext]:
    """Resolve authoritative edition and run contexts with timezone and cutoff."""
    edition_config = settings.get("edition", {})
    timezone = edition_config.get(
        "timezone", settings.get("pipeline", {}).get("timezone", "Asia/Kolkata")
    )
    local_date = started_at.astimezone(ZoneInfo(timezone)).date()
    cutoff_value = edition_config.get("publication_cutoff_local", "23:59:59")
    cutoff = time.fromisoformat(cutoff_value) if isinstance(cutoff_value, str) else cutoff_value

    edition = build_edition_context(
        local_date,
        EditionType(str(edition_config.get("type", "NIGHT")).upper()),
        timezone,
        cutoff,
        versions,
    )
    run = RunContext.create(edition, started_at)
    return replace(edition, run_id=run.run_id), run
