from __future__ import annotations

from typing import Any


def select_theme(classification: dict[str, Any], themes: list[dict[str, Any]], item: dict[str, Any]) -> dict[str, Any]:
    """Resolve exact micro-topic, topic, domain, then global themes in that order."""
    stream = "video" if item.get("kind") == "youtube" else "news"
    candidates: list[tuple[int, dict[str, Any]]] = []
    for theme in themes:
        if theme.get("id") == "domain-fallback":
            continue
        if theme.get("domain", "all") not in {"all", classification["domain"]}:
            continue
        streams = theme.get("content_stream", ["all"])
        if isinstance(streams, str):
            streams = [streams]
        if "all" not in streams and stream not in streams:
            continue
        micro = theme.get("micro_topic", "any")
        topic = theme.get("topic", "any")
        if micro not in {"any", classification["micro_topic"]}:
            continue
        if topic not in {"any", classification.get("topic"), classification.get("topic_key")}:
            continue
        if micro == classification["micro_topic"]:
            level, resolution = 4, "exact_micro_topic"
        elif topic not in {"any", None}:
            level, resolution = 3, "topic_fallback"
        elif theme.get("domain", "all") == classification["domain"]:
            level, resolution = 2, "domain_family"
        else:
            level, resolution = 1, "global_fallback"
        candidates.append((level, {**theme, "resolution_level": resolution, "fallback_used": level < 4}))
    if candidates:
        best_level = max(level for level, _ in candidates)
        best = [theme for level, theme in candidates if level == best_level]
        if len(best) > 1:
            best.sort(key=lambda theme: (-int(theme.get("priority", 0)), str(theme.get("id", ""))))
        selected = best[0]
        if stream == "video" and "main_argument" not in selected.get("questions", []):
            selected = {**selected, "questions": [*selected.get("questions", []), "main_argument", "claims", "methods", "limitations"]}
        return selected
    # A controlled configured fallback is explicit and observable; no theme is invented.
    fallback = next((theme for theme in themes if theme.get("id") == "domain-fallback"), {})
    if not fallback:
        raise ValueError(f"No configured theme or controlled fallback for {classification['micro_topic']}")
    return {
        **fallback,
        "domain": classification["domain"],
        "topic": classification.get("topic", ""),
        "micro_topic": classification["micro_topic"],
        "content_stream": [stream],
        "questions": fallback.get("content_streams", {}).get(stream, {}).get("questions", fallback.get("questions", [])),
        "resolution_level": "controlled_fallback",
        "fallback_used": True,
    }


def analysis_profile(classification: dict[str, Any], theme: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    stream = "video" if item.get("kind") == "youtube" else "news"
    return {
        "domain": classification["domain"], "topic": classification["topic"],
        "micro_topic": classification["micro_topic"], "content_stream": stream,
        "content_type": item.get("metadata", {}).get("content_type", item.get("kind", "news")),
        "theme": theme.get("id", "domain-fallback"), "questions": theme.get("questions", []),
        "evidence_rules": theme.get("evidence", {}), "output": theme.get("output", {}),
        "theme_resolution_level": theme.get("resolution_level", "unknown"),
        "fallback_used": bool(theme.get("fallback_used", False)),
        "analysis_contract": theme.get("analysis_contract", {}),
        "video_requirements": theme.get("content_streams", {}).get("video", {}).get("questions", []) if stream == "video" else [],
    }
