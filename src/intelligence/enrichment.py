from __future__ import annotations

import re
from collections import Counter
from typing import Any


ENTITY_PATTERNS = {
    "company": r"\b(?:OpenAI|Google|Microsoft|Apple|Amazon|Meta|NVIDIA|Anthropic|Tesla|IBM)\b",
    "country": r"\b(?:India|United States|China|Japan|Taiwan|Russia|Ukraine|Germany|France|United Kingdom)\b",
    "technology": r"\b(?:AI|LLM|GPU|CPU|RAG|Kubernetes|Python|semiconductor|cybersecurity)\b",
}


def extract_entities(text: str, registry: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    entities: list[dict[str, str]] = []
    for entry in registry or []:
        name = str(entry.get("name", "")).strip()
        aliases = entry.get("aliases", [name])
        if name and any(re.search(rf"(?<!\w){re.escape(str(alias))}(?!\w)", text, re.IGNORECASE) for alias in aliases):
            entities.append({"name": name, "type": str(entry.get("type", "organization"))})
    for entity_type, pattern in ENTITY_PATTERNS.items():
        entities.extend({"name": match, "type": entity_type} for match in sorted(set(re.findall(pattern, text, re.IGNORECASE))))
    return list({(entity["name"].lower(), entity["type"]): entity for entity in entities}.values())


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
    opportunity_markers = (
        "apply", "application", "eligible", "eligibility", "deadline", "open call",
        "submissions", "accepting", "program", "programme", "selected participants",
    )
    url_matches = re.findall(r"https?://[^\s)]+", f"{item.get('text', '')} {item.get('url', '')}")
    deadline = next(
        (match for match in re.findall(
            r"(?:deadline|applications? close|apply by)\s*[:\-]?\s*([A-Za-z0-9 ,/-]{4,40})",
            f"{item.get('title', '')} {item.get('text', '')}", re.IGNORECASE,
        )),
        "unknown",
    ).strip(" .,;")
    eligibility = next(
        (match.strip() for match in re.findall(
            r"(?:eligible|eligibility)\s*[:\-]?\s*([^.;]{8,160})",
            f"{item.get('title', '')} {item.get('text', '')}", re.IGNORECASE,
        )),
        "unknown",
    )
    value = next(
        (match for match in re.findall(r"(?:[$€£₹]\s?\d[\d,.]*\s?(?:m|k|million|thousand)?)", f"{item.get('title', '')} {item.get('text', '')}", re.IGNORECASE)),
        "unknown",
    )
    opportunities = []
    for category, keywords in categories.items():
        if any(keyword in text for keyword in keywords) and (
            any(marker in text for marker in opportunity_markers)
            or bool(analysis.get("opportunities"))
        ):
            issuer = next(
                (entity["name"] for entity in extract_entities(item.get("text", "")) if entity["type"] in {"company", "organization", "government"}),
                "unknown",
            )
            field_count = sum(value != "unknown" for value in (issuer, deadline, eligibility, value))
            opportunities.append({
                "type": category,
                "title": item.get("title", ""),
                "description": analysis.get("interpretation", [""])[0] if analysis.get("interpretation") else "",
                "issuer": issuer, "deadline": deadline, "eligibility": eligibility, "value": value,
                "application_url": url_matches[-1] if len(url_matches) > 1 else "unknown",
                "source": item.get("url", ""), "confidence_score": round(min(1.0, 0.35 + field_count * 0.12), 2),
                "why_relevant": "The source contains an explicit opportunity marker and a qualifying category.",
                "recommended_action": "Verify eligibility, deadline, value, and the official application details at the source.",
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
    topics = Counter(
        topic.get("key", topic.get("name", "")) if isinstance(topic, dict) else topic
        for item in items
        for topic in item.get("topics", [])
    )
    entities = Counter(entity.get("name") for item in items for entity in item.get("entities", []))
    return [
        {"type": "repeated_topic", "key": key, "evidence_count": count, "confidence": min(count / 5, 1.0)}
        for key, count in topics.items() if count >= 2
    ] + [
        {"type": "repeated_entity", "key": key, "evidence_count": count, "confidence": min(count / 5, 1.0)}
        for key, count in entities.items() if key and count >= 2
    ]
