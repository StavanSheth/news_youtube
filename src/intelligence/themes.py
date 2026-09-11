from __future__ import annotations

from typing import Any
import json
import re


def theme_fingerprint(theme: dict[str, Any]) -> str:
    """Fingerprint meaningful theme content while ignoring routing IDs."""
    meaningful = {
        key: theme.get(key)
        for key in ("objective", "questions", "retrieval_intent", "evidence", "output", "watch_items", "disambiguation_focus", "analysis_contract")
        if theme.get(key) not in (None, "", [], {})
    }
    normalized = re.sub(r"\s+", " ", json.dumps(meaningful, sort_keys=True, ensure_ascii=True).lower()).strip()
    return normalized


def _theme_tokens(theme: dict[str, Any], field: str) -> set[str]:
    value = theme.get(field, "")
    text = json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
    return {token for token in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", text.lower()) if token not in {"what", "should", "with", "from", "that", "this"}}


def theme_semantic_overlap(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    fields = ("analysis_contract", "questions", "retrieval_intent", "evidence", "output", "watch_items", "disambiguation_focus")
    overlaps = {}
    for field in fields:
        a, b = _theme_tokens(left, field), _theme_tokens(right, field)
        overlaps[field] = round(len(a & b) / max(1, len(a | b)), 3)
    score = round(sum(overlaps.values()) / len(fields), 3)
    return {"score": score, "fields": overlaps, "flag": score >= 0.85}


def theme_specificity_score(theme: dict[str, Any]) -> float:
    fields = ("analysis_contract", "questions", "retrieval_intent", "evidence", "output", "watch_items", "disambiguation_focus")
    populated = sum(bool(_theme_tokens(theme, field)) for field in fields)
    specific = len(_theme_tokens(theme, "retrieval_intent") | _theme_tokens(theme, "watch_items") | _theme_tokens(theme, "disambiguation_focus"))
    return round(min(1.0, populated / len(fields) * 0.6 + min(1.0, specific / 20) * 0.4), 3)


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
        selected = {**selected, "theme_id": selected.get("id"), "theme_specificity_score": theme_specificity_score(selected), "fallback_reason": None if not selected.get("fallback_used") else "exact_theme_missing"}
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
        "theme_id": fallback.get("id", "domain-fallback"),
        "fallback_reason": "no_exact_topic_or_domain_theme",
        "theme_specificity_score": theme_specificity_score(fallback),
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
        "retrieval_intent": theme.get("retrieval_intent", {}),
        "watch_items": theme.get("watch_items", []),
        "video_requirements": theme.get("content_streams", {}).get("video", {}).get("questions", []) if stream == "video" else [],
    }
