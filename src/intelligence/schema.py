from __future__ import annotations

from collections.abc import Iterable
from typing import Any

ANALYSIS_FIELDS = (
    "facts", "important_numbers", "claims", "interpretation", "changes", "implications",
    "risks", "opportunities", "actionable_insights", "uncertainties",
)

EVIDENCE_TYPES = {"fact", "official_statement", "reported_claim", "opinion", "inference", "speculation"}


def normalized_analysis(payload: Any) -> dict[str, Any]:
    """Validate and normalize a Gemini JSON object before it enters state or output."""
    if not isinstance(payload, dict):
        raise TypeError("Gemini response must be a JSON object")
    result: dict[str, Any] = {}
    for field in ANALYSIS_FIELDS:
        value = payload.get(field, [])
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"Gemini field {field!r} must be a list of strings")
        result[field] = list(dict.fromkeys(item.strip() for item in value if item.strip()))
    routine = payload.get("routine")
    if routine is not None and (
        not isinstance(routine, dict)
        or not all(isinstance(k, str) and isinstance(v, list) and all(isinstance(x, str) for x in v) for k, v in routine.items())
    ):
        raise ValueError("Gemini routine must be null or an object of string lists")
    result["routine"] = routine or None
    confidence = payload.get("confidence", 0.0)
    if not isinstance(confidence, (int, float)):
        raise ValueError("Gemini confidence must be numeric")
    result["confidence"] = max(0.0, min(float(confidence), 1.0))
    evidence = payload.get("evidence", [])
    if not isinstance(evidence, list):
        raise ValueError("Gemini evidence must be a list")
    normalized_evidence = []
    for entry in evidence:
        if isinstance(entry, str):
            entry = {"type": "fact", "text": entry}
        if not isinstance(entry, dict) or not isinstance(entry.get("text", ""), str):
            raise ValueError("Gemini evidence entries must be objects with text")
        evidence_type = {"claim": "reported_claim"}.get(entry.get("type", "fact"), entry.get("type", "fact"))
        if evidence_type not in EVIDENCE_TYPES:
            raise ValueError(f"Unsupported evidence type: {evidence_type}")
        normalized_evidence.append({
            "type": evidence_type, "text": entry["text"].strip(),
            "source_url": str(entry.get("source_url", "")).strip(),
        })
    result["evidence"] = [entry for entry in normalized_evidence if entry["text"]]
    return result


def merge_unique(values: Iterable[Iterable[str]]) -> list[str]:
    return list(dict.fromkeys(value for group in values for value in group if value))
