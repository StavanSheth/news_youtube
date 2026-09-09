from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any


def _tokens(title: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]{4,}", title.lower()) if token not in {"this", "that", "with", "from", "after", "into"}}


def group_events(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group likely reports of one event using stable URL/hash/title signals."""
    groups: list[dict[str, Any]] = []
    for item in items:
        tokens = _tokens(item.get("title", ""))
        match = next((group for group in groups if group["urls"] & {item.get("url", "")} or group["hashes"] & {item.get("content_hash", "")} or len(tokens & group["tokens"]) >= 3), None)
        if match is None:
            match = {"event_id": "event-" + hashlib.sha256(item["id"].encode()).hexdigest()[:16], "items": [], "urls": set(), "hashes": set(), "tokens": set()}
            groups.append(match)
        match["items"].append(item)
        match["urls"].add(item.get("url", ""))
        match["hashes"].add(item.get("content_hash", ""))
        match["tokens"].update(tokens)
    for group in groups:
        sources = {item.get("source", "") for item in group["items"]}
        group["corroboration"] = {"source_count": len(sources), "independent_sources": sorted(source for source in sources if source)}
        group["entities"] = sorted({entity for item in group["items"] for entity in item.get("metadata", {}).get("entities", [])})
        group["related_sources"] = [
            {key: item.get(key, "") for key in ("source", "url", "title")}
            for item in group["items"]
        ]
        group.pop("urls", None); group.pop("hashes", None); group.pop("tokens", None)
    return groups


def trend_signal(groups: list[dict[str, Any]], recent_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = defaultdict(int)
    for item in recent_items:
        for topic in item.get("topics", []):
            counts[topic] += 1
    return [{"type": "repeated_topic", "topic": topic, "evidence_count": count, "confidence": min(count / 5, 1.0)} for topic, count in counts.items() if count >= 2]


def importance(score: float, corroboration: int, novelty: float = 1.0) -> int:
    return max(0, min(100, round(score * 70 + min(corroboration, 3) * 7 + novelty * 9)))
