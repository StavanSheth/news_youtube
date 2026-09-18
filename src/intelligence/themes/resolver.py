"""Theme parameter and profile resolver."""

from __future__ import annotations

from typing import Any


def analysis_profile(
    classification: dict[str, Any],
    theme: dict[str, Any],
    item: dict[str, Any],
) -> dict[str, Any]:
    """Create authoritative analysis profile binding classification, theme, and stream requirements."""
    stream = "video" if item.get("kind") == "youtube" else "news"
    return {
        "domain": classification.get("domain", ""),
        "topic": classification.get("topic", ""),
        "micro_topic": classification.get("micro_topic", ""),
        "content_stream": stream,
        "content_type": item.get("metadata", {}).get("content_type", item.get("kind", "news")),
        "theme": theme.get("id", "domain-fallback"),
        "theme_id": theme.get("id", "domain-fallback"),
        "questions": theme.get("questions", []),
        "evidence_rules": theme.get("evidence", {}),
        "output": theme.get("output", {}),
        "theme_resolution_level": theme.get("resolution_level", "unknown"),
        "fallback_used": bool(theme.get("fallback_used", False)),
        "theme_resolution": theme.get("theme_resolution", {}),
        "analysis_contract": theme.get("analysis_contract", {}),
        "retrieval_intent": theme.get("retrieval_intent", {}),
        "watch_items": theme.get("watch_items", []),
        "video_requirements": (
            theme.get("content_streams", {}).get("video", {}).get("questions", [])
            if stream == "video"
            else []
        ),
    }
