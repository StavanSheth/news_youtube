from __future__ import annotations

import re
from collections import Counter
from typing import Any


ENTITY_PATTERNS = {
    "company": r"\b(?:OpenAI|Google|Microsoft|Apple|Amazon|Meta|NVIDIA|Anthropic|Tesla|IBM)\b",
    "country": r"\b(?:India|United States|China|Japan|Taiwan|Russia|Ukraine|Germany|France|United Kingdom)\b",
    "technology": r"\b(?:AI|LLM|GPU|CPU|RAG|Kubernetes|Python|semiconductor|cybersecurity)\b",
}


def extract_entities(text: str) -> list[dict[str, str]]:
    entities: list[dict[str, str]] = []
    for entity_type, pattern in ENTITY_PATTERNS.items():
        entities.extend({"name": match, "type": entity_type} for match in sorted(set(re.findall(pattern, text, re.IGNORECASE))))
    return entities


def detect_opportunities(item: dict[str, Any], analysis: dict[str, Any]) -> list[dict[str, Any]]:
    text = f"{item.get('title', '')} {item.get('text', '')}".lower()
    categories = {
        "grant": ("grant", "grants"),
        "fellowship": ("fellowship", "fellowships"),
        "scholarship": ("scholarship", "scholarships"),
        "accelerator": ("accelerator", "accelerators"),
        "hackathon": ("hackathon", "hackathons"),
        "funding": ("funding", "investment", "series a", "series b"),
        "tender": ("tender", "procurement"),
    }
    opportunities = []
    for category, keywords in categories.items():
        if any(keyword in text for keyword in keywords):
            opportunities.append({
                "type": category,
                "title": item.get("title", ""),
                "description": analysis.get("interpretation", [""])[0] if analysis.get("interpretation") else "",
                "issuer": next((entity["name"] for entity in extract_entities(item.get("text", "")) if entity["type"] == "company"), "unknown"),
                "deadline": "unknown",
                "eligibility": "unknown",
                "value": "unknown",
                "source": item.get("url", ""),
                "confidence_score": 0.5,
                "recommended_action": "Verify eligibility, deadline, and official application details at the source.",
            })
    return opportunities


def confidence_score(item: dict[str, Any], analysis: dict[str, Any], corroboration: int = 1) -> float:
    evidence = min(len(analysis.get("facts", [])) / 5, 1.0)
    extraction = 1.0 if item.get("text") else 0.0
    source = min(float(item.get("priority", 1)) / 10, 1.0)
    corroboration_signal = min(corroboration / 3, 1.0)
    model = float(analysis.get("confidence", 0.0))
    return round(max(0.0, min(1.0, evidence * 0.3 + extraction * 0.2 + source * 0.15 + corroboration_signal * 0.15 + model * 0.2)), 3)


def trend_signals(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    topics = Counter(topic for item in items for topic in item.get("topics", []))
    entities = Counter(entity.get("name") for item in items for entity in item.get("entities", []))
    return [
        {"type": "repeated_topic", "key": key, "evidence_count": count, "confidence": min(count / 5, 1.0)}
        for key, count in topics.items() if count >= 2
    ] + [
        {"type": "repeated_entity", "key": key, "evidence_count": count, "confidence": min(count / 5, 1.0)}
        for key, count in entities.items() if key and count >= 2
    ]
