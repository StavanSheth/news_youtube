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
    priority: int = 5
    review_status: str = "AI_VALIDATED"
    objective: str = ""
    scope: dict[str, Any] = field(default_factory=dict)
    primary_questions: tuple[str, ...] = ()
    required_dimensions: tuple[str, ...] = ()
    forbidden_dimensions: tuple[str, ...] = ()
    retrieval_intent: dict[str, Any] = field(default_factory=dict)
    evidence_requirements: tuple[str, ...] = ()
    significance_rules: dict[str, Any] = field(default_factory=dict)
    entity_extraction: dict[str, Any] = field(default_factory=dict)
    event_extraction: dict[str, Any] = field(default_factory=dict)
    analysis_dimensions: tuple[str, ...] = ()
    action_rules: dict[str, Any] = field(default_factory=dict)
    watch_rules: dict[str, Any] = field(default_factory=dict)
    decision_criteria: dict[str, Any] = field(default_factory=dict)
    watch_indicators: tuple[str, ...] = ()
    output_requirements: dict[str, Any] = field(default_factory=dict)
    stream_rules: dict[str, Any] = field(default_factory=dict)
    no_update_policy: dict[str, Any] = field(default_factory=dict)
    trend_rules: dict[str, Any] = field(default_factory=dict)
    source_preferences: dict[str, Any] = field(default_factory=dict)
    uncertainty_rules: dict[str, Any] = field(default_factory=dict)
    analysis_contract: dict[str, Any] = field(default_factory=dict)

    def validate_diagnostics(self) -> dict[str, Any]:
        """Return structured machine-checkable diagnostics per Section 4.2."""
        missing_fields: list[str] = []
        warnings: list[str] = []

        if not self.theme_id:
            missing_fields.append("theme_id")
        if not self.version:
            missing_fields.append("version")
        if not self.primary_questions:
            missing_fields.append("questions")
        if not self.evidence_requirements:
            missing_fields.append("evidence_requirements")
        if not self.micro_topic_id:
            missing_fields.append("micro_topic_id")
        if not self.domain_id:
            missing_fields.append("domain_id")
        if not self.topic_id:
            warnings.append("topic_id is unspecified or generic")
        if not self.objective and not self.analysis_contract.get("objective"):
            missing_fields.append("objective")
        if not self.significance_rules:
            missing_fields.append("significance_rules")
        if not self.retrieval_intent:
            warnings.append("retrieval_intent is empty")
        if not self.stream_rules.get("news"):
            missing_fields.append("stream_rules.news")
        if not self.stream_rules.get("video"):
            missing_fields.append("stream_rules.video")
        if not self.no_update_policy:
            missing_fields.append("no_update_policy")
        if not self.entity_extraction:
            warnings.append("entity_requirements missing or empty")
        if not self.event_extraction:
            warnings.append("event_requirements missing or empty")
        if not self.action_rules:
            warnings.append("action_rules missing or empty")
        if not self.watch_indicators and not self.watch_rules:
            warnings.append("watch_indicators missing or empty")
        if not self.output_requirements:
            missing_fields.append("output_requirements")
        if not self.analysis_contract and not self.objective:
            missing_fields.append("analysis_contract")

        from .quality import theme_quality_score
        quality_score = theme_quality_score(self.to_dict())

        valid = len(missing_fields) == 0
        return {
            "theme_id": self.theme_id,
            "micro_topic_id": self.micro_topic_id or "",
            "valid": valid,
            "missing_fields": missing_fields,
            "warnings": warnings,
            "quality_score": quality_score,
        }

    def validate_completeness(self) -> tuple[bool, list[str]]:
        """Validate basic machine-checkable completeness."""
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

    def validate_set_e_completeness(self) -> tuple[bool, list[str]]:
        """Strict Set-E section 5 completeness check."""
        ok, errors = self.validate_completeness()
        strict_errors = list(errors)
        if not self.micro_topic_id:
            strict_errors.append("Theme missing micro_topic_id")
        if not self.significance_rules:
            strict_errors.append("Theme missing significance_rules")
        if not self.stream_rules:
            strict_errors.append("Theme missing stream_rules")
        if not self.no_update_policy:
            strict_errors.append("Theme missing no_update_policy")
        return len(strict_errors) == 0, strict_errors

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ThemeContract:
        questions = data.get("questions") or data.get("primary_questions") or ()
        evidence = data.get("evidence_requirements")
        if isinstance(evidence, (list, tuple)):
            evidence_tuple = tuple(evidence)
        elif isinstance(evidence, dict):
            evidence_tuple = tuple(evidence.get("required", []))
        elif isinstance(data.get("evidence"), dict):
            evidence_tuple = tuple(data["evidence"].get("required", []))
        else:
            evidence_tuple = ()

        raw_actions = data.get("action_rules", {})
        action_rules = raw_actions if isinstance(raw_actions, dict) else {"rules": list(raw_actions)} if isinstance(raw_actions, (list, tuple)) else {}
        raw_output = data.get("output_requirements") or data.get("output", {})
        output_reqs = raw_output if isinstance(raw_output, dict) else {"requirements": list(raw_output)} if isinstance(raw_output, (list, tuple)) else {}

        return cls(
            theme_id=str(data.get("theme_id") or data.get("id", "")),
            micro_topic_id=data.get("micro_topic_id") or data.get("micro_topic"),
            domain_id=data.get("domain_id") or data.get("domain"),
            topic_id=data.get("topic_id") or data.get("topic"),
            version=str(data.get("version", "1.0.0")),
            priority=int(data.get("priority", 5)),
            review_status=str(data.get("review_status", "AI_VALIDATED")),
            objective=str(data.get("objective") or data.get("analysis_contract", {}).get("objective", "")),
            scope=dict(data.get("scope", {})),
            primary_questions=tuple(questions),
            required_dimensions=tuple(data.get("required_dimensions", ())),
            forbidden_dimensions=tuple(data.get("forbidden_dimensions", ())),
            retrieval_intent=dict(data.get("retrieval_intent", {})),
            evidence_requirements=evidence_tuple,
            significance_rules=dict(data.get("significance_rules", {})),
            entity_extraction=dict(data.get("entity_extraction") or data.get("entity_fields", {})),
            event_extraction=dict(data.get("event_extraction") or data.get("event_fields", {})),
            analysis_dimensions=tuple(data.get("analysis_dimensions", ())),
            action_rules=action_rules,
            watch_rules=dict(data.get("watch_rules", {})),
            decision_criteria=dict(data.get("decision_criteria", {})),
            watch_indicators=tuple(data.get("watch_indicators") or data.get("watch_items", ())),
            output_requirements=output_reqs,
            stream_rules=dict(data.get("stream_rules") or data.get("content_streams", {})),
            no_update_policy=dict(data.get("no_update_policy", {})),
            trend_rules=dict(data.get("trend_rules", {})),
            source_preferences=dict(data.get("source_preferences", {})),
            uncertainty_rules=dict(data.get("uncertainty_rules", {})),
            analysis_contract=dict(data.get("analysis_contract", {}) or ({"objective": data.get("objective", "")} if data.get("objective") else {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.theme_id,
            "theme_id": self.theme_id,
            "micro_topic_id": self.micro_topic_id,
            "domain": self.domain_id,
            "domain_id": self.domain_id,
            "topic": self.topic_id,
            "topic_id": self.topic_id,
            "version": self.version,
            "priority": self.priority,
            "review_status": self.review_status,
            "objective": self.objective,
            "scope": self.scope,
            "questions": list(self.primary_questions),
            "primary_questions": list(self.primary_questions),
            "required_dimensions": list(self.required_dimensions),
            "forbidden_dimensions": list(self.forbidden_dimensions),
            "retrieval_intent": self.retrieval_intent,
            "evidence_requirements": list(self.evidence_requirements),
            "evidence": {"required": list(self.evidence_requirements)},
            "significance_rules": self.significance_rules,
            "entity_extraction": self.entity_extraction,
            "event_extraction": self.event_extraction,
            "analysis_dimensions": list(self.analysis_dimensions),
            "action_rules": self.action_rules,
            "watch_rules": self.watch_rules,
            "decision_criteria": self.decision_criteria,
            "watch_indicators": list(self.watch_indicators),
            "watch_items": list(self.watch_indicators),
            "output_requirements": self.output_requirements,
            "output": self.output_requirements,
            "stream_rules": self.stream_rules,
            "content_streams": self.stream_rules,
            "no_update_policy": self.no_update_policy,
            "trend_rules": self.trend_rules,
            "source_preferences": self.source_preferences,
            "uncertainty_rules": self.uncertainty_rules,
            "analysis_contract": self.analysis_contract or {"objective": self.objective},
        }


def validate_theme_contract(theme: ThemeContract | dict[str, Any]) -> dict[str, Any]:
    """Canonical completeness and quality diagnostics for a theme contract."""
    contract = theme if isinstance(theme, ThemeContract) else ThemeContract.from_dict(theme)
    return contract.validate_diagnostics()


@dataclass(frozen=True)
class ThemeResolution:
    """Deterministic theme resolution and observable fallback trace."""

    requested_level: str
    resolved_level: str
    fallback_used: bool = False
    fallback_reason: str | None = None
    theme_id: str = ""
    micro_topic_id: str = ""
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
            "micro_topic_id": self.micro_topic_id,
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
            "micro_topic_id": self.micro_topic_id,
            "resolution_level_code": level_code,
            "resolution_level": self.resolved_level,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "theme_specificity_score": self.specificity_score,
            "theme_origin": self.theme_origin,
            "theme_quality_score": self.quality_score,
        }
