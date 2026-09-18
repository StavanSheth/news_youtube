"""Pydantic schemas for structured AI analysis outputs and claims."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from ..schema import normalized_analysis


class EvidenceTypeEnum(StrEnum):
    """Categorized evidence and claim tiers."""

    FACT = "fact"
    OFFICIAL_STATEMENT = "official_statement"
    REPORTED_CLAIM = "reported_claim"
    OPINION = "opinion"
    INFERENCE = "inference"
    SPECULATION = "speculation"


class EvidenceItem(BaseModel):
    """Grounded evidence citation linking extracted text to source URL."""

    model_config = ConfigDict(extra="ignore")

    type: str = Field(default=EvidenceTypeEnum.FACT.value, description="Categorized evidence type")
    text: str = Field(description="Direct quotation or faithful paraphrase from source evidence")
    source_url: str = Field(default="", description="Source URL where evidence was located")


class FactClaim(BaseModel):
    """Verified factual statement grounded in primary or secondary evidence."""

    model_config = ConfigDict(extra="ignore")

    statement: str
    source_url: str = ""
    evidence_type: str = EvidenceTypeEnum.FACT.value


class InterpretationClaim(BaseModel):
    """Domain interpretation or synthesis derived from reported facts."""

    model_config = ConfigDict(extra="ignore")

    statement: str
    implication_type: str = "interpretation"


class ActionableInsight(BaseModel):
    """Forward-looking action, verification step, or monitoring suggestion."""

    model_config = ConfigDict(extra="ignore")

    insight: str
    time_horizon: str = "immediate"


class AnalysisOutput(BaseModel):
    """Authoritative structured Pydantic schema for Gemini micro-topic analysis."""

    model_config = ConfigDict(extra="ignore")

    facts: list[str] = Field(default_factory=list, description="Direct factual observations verified from source")
    important_numbers: list[str] = Field(default_factory=list, description="Specific figures, metrics, percentages, dollar amounts")
    claims: list[str] = Field(default_factory=list, description="Attributed third-party claims or vendor statements")
    interpretation: list[str] = Field(default_factory=list, description="Contextual meaning, relevance, and implications")
    changes: list[str] = Field(default_factory=list, description="What specifically changed compared to baseline")
    implications: list[str] = Field(default_factory=list, description="Broader industry or technological implications")
    risks: list[str] = Field(default_factory=list, description="Identified risks, caveats, or failure modes")
    opportunities: list[str] = Field(default_factory=list, description="Strategic opportunities or advantageous avenues")
    actionable_insights: list[str] = Field(default_factory=list, description="Concrete next steps or watchpoint items")
    uncertainties: list[str] = Field(default_factory=list, description="Known unknowns or missing verification points")
    routine: dict[str, list[str]] | None = Field(default=None, description="Routine operational classifications")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Overall analysis confidence score (0.0 - 1.0)")
    evidence: list[EvidenceItem] = Field(default_factory=list, description="Citations supporting the analysis")

    def to_normalized_dict(self) -> dict[str, Any]:
        """Convert to fully normalized repository format passing normalized_analysis contract."""
        data = self.model_dump()
        return normalized_analysis(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnalysisOutput":
        """Construct from raw or normalized dictionary."""
        norm = normalized_analysis(data)
        return cls(**norm)
