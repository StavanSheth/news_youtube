from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any
from urllib.parse import urlparse

from .enrichment import extract_entities


def _tokens(title: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]{4,}", title.lower()) if token not in {"this", "that", "with", "from", "after", "into"}}


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _title_key(title: str) -> str:
    return " ".join(sorted(_tokens(title)))


def group_events(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group likely reports of one event using stable URL/hash/title signals."""
    groups: list[dict[str, Any]] = []
    for item in items:
        tokens = _tokens(item.get("title", ""))
        entity_keys = {entity["name"].lower() for entity in extract_entities(f"{item.get('title', '')}\n{item.get('text', '')}")}
        url = item.get("url", "")
        content_hash = item.get("content_hash", "")
        match = next(
            (
                group
                for group in groups
                if (url and group["urls"] & {url})
                or (content_hash and group["hashes"] & {content_hash})
                or (entity_keys and group["entity_keys"] & entity_keys and len(tokens & group["tokens"]) >= 1)
                or len(tokens & group["tokens"]) >= 3
            ),
            None,
        )
        if match is None:
            match = {"event_id": "event-" + hashlib.sha256(item["id"].encode()).hexdigest()[:16], "items": [], "urls": set(), "hashes": set(), "tokens": set(), "entity_keys": set()}
            groups.append(match)
        match["items"].append(item)
        match["urls"].add(item.get("url", ""))
        if content_hash:
            match["hashes"].add(content_hash)
        match["tokens"].update(tokens)
        match["entity_keys"].update(entity_keys)
    for group in groups:
        sources = {item.get("source", "") for item in group["items"] if item.get("source")}
        title_keys = defaultdict(list)
        for item in group["items"]:
            title_keys[_title_key(item.get("title", ""))].append(item)
        syndicated = []
        for copies in title_keys.values():
            if len(copies) > 1:
                syndicated.extend(item.get("source", "") for item in copies[1:] if item.get("source"))
        syndicated = sorted(set(syndicated))
        independent = sorted(source for source in sources if source not in syndicated)
        group["corroboration"] = {
            "source_count": len(independent),
            "independent_sources": independent,
            "syndicated_sources": syndicated,
            "source_hosts": sorted({_host(item.get("url", "")) for item in group["items"] if item.get("url")}),
            "has_primary": any(item.get("metadata", {}).get("trust_tier") == 1 for item in group["items"]),
        }
        group["entities"] = sorted(group["entity_keys"])
        group["related_sources"] = [
            {key: item.get(key, "") for key in ("source", "url", "title")}
            for item in group["items"]
        ]
        group.pop("urls", None)
        group.pop("hashes", None)
        group.pop("tokens", None)
        group.pop("entity_keys", None)
    return groups


def trend_signal(groups: list[dict[str, Any]], recent_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = defaultdict(int)
    for item in recent_items:
        for topic in item.get("topics", []):
            counts[topic] += 1
    return [{"type": "repeated_topic", "topic": topic, "evidence_count": count, "confidence": min(count / 5, 1.0)} for topic, count in counts.items() if count >= 2]


def importance(
    score: float,
    corroboration: int,
    novelty: float = 1.0,
    weights: dict[str, float] | None = None,
) -> int:
    configured = {"relevance": 0.60, "corroboration": 0.15, "novelty": 0.10, "strategic_impact": 0.15}
    configured.update(weights or {})
    strategic_impact = min(1.0, max(0.0, score))
    total = (
        max(0.0, min(1.0, score)) * configured["relevance"]
        + min(corroboration, 3) / 3 * configured["corroboration"]
        + max(0.0, min(1.0, novelty)) * configured["novelty"]
        + strategic_impact * configured["strategic_impact"]
    )
    return max(0, min(100, round(total * 100)))
