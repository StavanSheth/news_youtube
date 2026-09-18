"""Profile resolution and compiler delegation for micro-topics."""

from __future__ import annotations

from typing import Any
from ..profiles import compile_semantic_profile, profile_quality, resolve_microtopic_profile


def profile_for(domain: str, micro_topic: str, profiles: dict[str, Any] | None) -> dict[str, Any]:
    profiles = profiles or {}
    defaults = dict(profiles.get("defaults", {}))
    domain_config = profiles.get("domains", {}).get(domain, {})
    merged = {**defaults, **{key: value for key, value in domain_config.items() if key != "overrides"}}
    merged.update(domain_config.get("overrides", {}).get(micro_topic, {}))
    return merged


__all__ = [
    "compile_semantic_profile",
    "profile_for",
    "profile_quality",
    "resolve_microtopic_profile",
]
