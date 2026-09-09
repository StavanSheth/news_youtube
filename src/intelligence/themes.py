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
            level = 4
        elif topic not in {"any", None}:
            level = 3
        elif theme.get("domain", "all") == classification["domain"]:
            level = 2
        else:
            level = 1
        candidates.append((level, theme))
    if candidates:
        return max(candidates, key=lambda match: (match[0], int(match[1].get("priority", 0))))[1]
    # A configured fallback is still specialized at runtime, so taxonomy leaves never
    # collapse into one generic profile merely because YAML lacks a bespoke entry.
    fallback = next((theme for theme in themes if theme.get("id") == "domain-fallback"), {})
    report_type = "technical_deep_dive" if classification["domain"] in {
        "artificial-intelligence", "software-engineering", "cybersecurity", "semiconductors", "research"
    } else "executive_brief"
    return {
        **fallback,
        "id": f"{classification['domain']}-{classification['micro_topic']}-analysis",
        "domain": classification["domain"],
        "micro_topic": classification["micro_topic"],
        "priority": classification.get("priority", 1),
        "topic": classification.get("topic", ""),
        "content_stream": [stream],
        "questions": (
            ["main_argument", "claims", "methods", "tools", "workflows", "experiments", "practical_applications"]
            if stream == "video"
            else ["what_changed", "what_is_confirmed", "why_it_matters", "who_is_affected", "what_to_watch"]
        ),
        "evidence": {"required": ["fact"], "distinguish": ["fact", "official_statement", "reported_claim", "opinion", "inference", "speculation"]},
        "output": {"report_type": report_type, "sections": ["summary", "evidence", "implications", "actions", "sources"]},
    }


def analysis_profile(classification: dict[str, Any], theme: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    stream = "video" if item.get("kind") == "youtube" else "news"
    return {
        "domain": classification["domain"], "topic": classification["topic"],
        "micro_topic": classification["micro_topic"], "content_stream": stream,
        "content_type": item.get("metadata", {}).get("content_type", item.get("kind", "news")),
        "theme": theme.get("id", "domain-fallback"), "questions": theme.get("questions", []),
        "evidence_rules": theme.get("evidence", {}), "output": theme.get("output", {}),
        "video_requirements": ["main argument", "claims", "methods", "tools", "workflows", "experiments"] if stream == "video" else [],
    }
