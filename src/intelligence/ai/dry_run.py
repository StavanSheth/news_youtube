"""Deterministic local and mock AI providers for tests, benchmarks, and dry runs."""

from __future__ import annotations

from typing import Any

from ..contracts import EvidenceType, provenance_from_mapping
from ..identity import make_content_id, make_source_id
from ..schema import normalized_analysis
from .base import AIProvider
from .schemas import AnalysisOutput
from .usage import TokenUsage, calculate_cost, estimate_tokens


class DryRunProvider(AIProvider):
    """Deterministic local provider used by dry-run and fixture acceptance tests."""

    def __init__(self) -> None:
        self.call_history: list[dict[str, Any]] = []
        self.cumulative_usage = TokenUsage()

    def analyze_micro_topic(
        self,
        item: dict[str, Any],
        profile: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate deterministic structured analysis with full provenance."""
        if not evidence:
            res = normalized_analysis({"confidence": 0.0})
            self.call_history.append({"item": item, "evidence": evidence, "output": res})
            return res

        source_text = evidence[0].get("text", "").strip()
        fact = source_text[:360] or item.get("title", "Source item")
        stream = profile.get("content_stream", "news")
        interpretation = (
            f"The source is relevant to {profile.get('micro_topic', 'the selected micro-topic')} "
            f"and should be assessed as {stream} intelligence."
        )
        action = (
            "Verify the cited source and compare the next update against this baseline."
            if stream == "news"
            else "Review the transcript or description for the method, tool, and follow-up experiment."
        )

        raw_payload = {
            "facts": [fact],
            "changes": [f"The source reports: {fact[:220]}"],
            "interpretation": [interpretation],
            "actionable_insights": [action],
            "uncertainties": ["Fixture analysis is deterministic and does not replace provider review."],
            "confidence": 0.75,
            "evidence": [
                {"type": "fact", "text": fact, "source_url": item.get("url", "")}
            ],
        }
        structured = AnalysisOutput.from_dict(raw_payload)
        result = structured.to_normalized_dict()

        source_id = item.get("metadata", {}).get("source_id") or make_source_id(item.get("source", "unknown"))
        content_id = item.get("metadata", {}).get("content_id") or make_content_id(
            source_id, item.get("url", ""), item.get("title", ""), item.get("published_at", ""), item.get("text", "")
        )

        for entry in result["evidence"]:
            provenance = provenance_from_mapping(
                {
                    **item,
                    "metadata": {
                        **item.get("metadata", {}),
                        "content_id": content_id,
                        "source_id": source_id,
                    },
                },
                EvidenceType.OTHER,
                entry["text"],
            )
            entry.update({
                "provenance": provenance.to_dict(),
                "evidence_id": provenance.evidence_id,
                "content_id": content_id,
                "source_id": source_id,
            })

        # Track token usage
        prompt_tokens = estimate_tokens(source_text) + 200
        candidate_tokens = estimate_tokens(fact + interpretation + action)
        total_tokens = prompt_tokens + candidate_tokens
        call_cost = calculate_cost(prompt_tokens, candidate_tokens, model="gemini-2.5-flash")
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            candidate_tokens=candidate_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=call_cost,
        )
        self.cumulative_usage = self.cumulative_usage + usage

        self.call_history.append({
            "item": item,
            "profile": profile,
            "evidence": evidence,
            "output": result,
            "usage": usage,
        })
        return result


class FakeAIProvider(AIProvider):
    """Configurable mock AI provider for testing edge cases, latency, and error recoveries."""

    def __init__(
        self,
        responses: list[dict[str, Any]] | None = None,
        exception_to_raise: Exception | None = None,
    ) -> None:
        self.responses = list(responses or [])
        self.exception_to_raise = exception_to_raise
        self.calls: list[dict[str, Any]] = []

    def analyze_micro_topic(
        self,
        item: dict[str, Any],
        profile: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self.calls.append({"item": item, "profile": profile, "evidence": evidence})
        if self.exception_to_raise:
            raise self.exception_to_raise
        if self.responses:
            res = self.responses.pop(0)
            return normalized_analysis(res)
        dry = DryRunProvider()
        return dry.analyze_micro_topic(item, profile, evidence)
