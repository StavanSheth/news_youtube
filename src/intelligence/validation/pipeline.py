"""Canonical 5-stage validation pipeline orchestrating analysis verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .business import validate_business_rules
from .provenance import validate_claim_provenance
from .schema import validate_analysis_schema
from .semantic import validate_semantic_content
from .usefulness import validate_usefulness


@dataclass(frozen=True)
class ValidationResult:
    validation_status: str  # VALID, WARNING, INVALID
    schema_status: str      # PASS, FAIL
    semantic_status: str    # PASS, FAIL
    provenance_status: str  # PASS, FAIL
    business_status: str    # PASS, FAIL
    usefulness_status: str  # PASS, WARN
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def is_publishable(self) -> bool:
        return self.validation_status in {"VALID", "WARNING"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_status": self.validation_status,
            "schema_status": self.schema_status,
            "semantic_status": self.semantic_status,
            "provenance_status": self.provenance_status,
            "business_status": self.business_status,
            "usefulness_status": self.usefulness_status,
            "is_publishable": self.is_publishable,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def validate_analysis(
    analysis: dict[str, Any],
    micro_topic_job: Any | None = None,
    context_packet: Any | None = None,
) -> ValidationResult:
    """Execute canonical 5-stage validation pipeline: Schema -> Semantic -> Provenance -> Business -> Usefulness."""
    errors: list[str] = []
    warnings: list[str] = []

    # Stage 1: Schema Validation
    schema_ok, schema_errs = validate_analysis_schema(analysis)
    errors.extend(schema_errs)
    schema_status = "PASS" if schema_ok else "FAIL"

    # Resolve theme and classification from job or context
    theme: dict[str, Any] = {}
    classification: dict[str, Any] = {}
    if micro_topic_job:
        if isinstance(micro_topic_job, dict):
            theme = micro_topic_job.get("theme", {})
            classification = micro_topic_job.get("classification", {})
        elif hasattr(micro_topic_job, "theme"):
            theme = getattr(micro_topic_job, "theme", {})
            classification = {
                "micro_topic_id": getattr(micro_topic_job, "micro_topic_id", ""),
                "domain": getattr(micro_topic_job, "domain_id", ""),
            }

    # Stage 2: Semantic Validation
    semantic_ok, semantic_errs = validate_semantic_content(analysis, theme, classification)
    errors.extend(semantic_errs)
    semantic_status = "PASS" if semantic_ok else "FAIL"

    # Stage 3: Provenance Validation
    prov_ok, prov_errs = validate_claim_provenance(analysis, context_packet)
    errors.extend(prov_errs)
    provenance_status = "PASS" if prov_ok else "FAIL"

    # Stage 4: Business Rules Validation
    biz_ok, biz_errs = validate_business_rules(analysis)
    errors.extend(biz_errs)
    business_status = "PASS" if biz_ok else "FAIL"

    # Stage 5: Usefulness Validation
    use_ok, use_warns = validate_usefulness(analysis)
    warnings.extend(use_warns)
    usefulness_status = "PASS" if use_ok else "WARN"

    if errors:
        validation_status = "INVALID"
    elif warnings:
        validation_status = "WARNING"
    else:
        validation_status = "VALID"

    return ValidationResult(
        validation_status=validation_status,
        schema_status=schema_status,
        semantic_status=semantic_status,
        provenance_status=provenance_status,
        business_status=business_status,
        usefulness_status=usefulness_status,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
