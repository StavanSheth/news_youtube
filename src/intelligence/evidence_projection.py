"""Deterministic, bounded projections passed to the model."""

from __future__ import annotations

from typing import Any
import re


def project_micro_topic_context(
    item: dict[str, Any], classification: dict[str, Any], scope: Any, evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    content_id = scope.source_content_id
    spans = []
    provenance = []
    for chunk in evidence:
        metadata = chunk.get("metadata", {})
        text = chunk.get("text", "")
        if not metadata.get("span_id") and classification.get("signals"):
            sentences = re.split(r"(?<=[.!?])\s+", text)
            relevant = [sentence for sentence in sentences if any(str(signal).lower() in sentence.lower() for signal in classification.get("signals", []))]
            if relevant:
                text = " ".join(relevant)
        span = {
            "span_id": metadata.get("span_id", chunk.get("id", "")),
            "text": text,
            "source": metadata.get("provenance"),
        }
        spans.append(span)
        if span["source"]:
            provenance.append(span["source"])
    return {
        "content_id": content_id,
        "source_id": scope.source_id,
        "micro_topic_id": scope.micro_topic_id,
        "title": item.get("title", ""),
        "url": item.get("url", ""),
        "text": "\n\n".join(span["text"] for span in spans),
        "relevant_context": spans,
        "evidence_ids": [str(chunk.get("id", "")) for chunk in evidence],
        "provenance": provenance,
        "classification": {
            "micro_topic": classification.get("micro_topic", ""),
            "signals": classification.get("signals", []),
        },
        "metadata": scope.to_metadata(),
    }
