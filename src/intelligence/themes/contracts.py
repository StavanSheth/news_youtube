"""Theme contract models and machine-checkable specifications."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ThemeContract:
    """Authoritative machine-checkable theme contract."""

    theme_id: str
    micro_topic_id: str | None = None
    domain_id: str | None = None
    topic_id: str | None = None
    version: str = "1.0.0"
    objective: str = ""
    primary_questions: tuple[str, ...] = ()
    required_dimensions: tuple[str, ...] = ()
    forbidden_dimensions: tuple[str, ...] = ()
    retrieval_intent: dict[str, Any] = field(default_factory=dict)
    evidence_requirements: tuple[str, ...] = ()
    decision_criteria: dict[str, Any] = field(default_factory=dict)
    watch_indicators: tuple[str, ...] = ()
    output_requirements: dict[str, Any] = field(default_factory=dict)
    stream_rules: dict[str, Any] = field(default_factory=dict)
    no_update_policy: dict[str, Any] = field(default_factory=dict)

    def validate_completeness(self) -> tuple[bool, list[str]]:
        """Validate machine-checkable completeness per Set E theme specification."""
        errors = []
        if not self.theme_id:
            errors.append("Theme missing theme_id")
        if not self.version:
            errors.append("Theme missing version")
        if not self.primary_questions:
            errors.append("Theme primary_questions must contain at least 1 question")
        if not self.evidence_requirements:
            errors.append("Theme evidence_requirements must contain at least 1 requirement")
        return len(errors) == 0, errors


@dataclass(frozen=True)
class ThemeResolution:
    """Deterministic theme resolution and observable fallback trace."""

    requested_level: str
    resolved_level: str
    fallback_used: bool = False
    fallback_reason: str | None = None
    theme_id: str = ""
    specificity_score: float = 1.0
    theme_origin: str = "CURATED"
    quality_score: float = 0.0
    matched_pattern: str = ""
    stream_parameters: dict[str, Any] = field(default_factory=dict)
    questions: tuple[str, ...] = ()
    analysis_contract: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_level": self.requested_level,
            "resolved_level": self.resolved_level,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "theme_id": self.theme_id,
            "theme_specificity_score": self.specificity_score,
            "theme_origin": self.theme_origin,
            "theme_quality_score": self.quality_score,
            "matched_pattern": self.matched_pattern,
            "stream_parameters": self.stream_parameters,
            "questions": list(self.questions),
            "analysis_contract": self.analysis_contract,
        }

    def to_metadata(self) -> dict[str, Any]:
        level_code = {
            "micro_topic": "EXACT_MICRO_TOPIC",
            "topic": "TOPIC_FALLBACK",
            "domain": "DOMAIN_FALLBACK",
            "controlled_fallback": "CONTROLLED_FALLBACK",
        }.get(self.resolved_level, self.resolved_level.upper())
        if self.resolved_level == "micro_topic" and self.theme_origin in {"DERIVED", "TEMPLATE_DERIVED"}:
            level_code = "DERIVED_EXACT"
        elif self.resolved_level == "micro_topic":
            level_code = "CURATED_EXACT"

        return {
            "theme_id": self.theme_id,
            "resolution_level_code": level_code,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "theme_specificity_score": self.specificity_score,
            "theme_origin": self.theme_origin,
            "theme_quality_score": self.quality_score,
        }
