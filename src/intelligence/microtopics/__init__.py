"""Micro-topic intelligence engine package."""

from __future__ import annotations

from .catalog import catalog, validate_microtopic_coverage
from .classifier import MicroTopicClassificationEngine, classify_micro_topics
from .coverage import CANONICAL_COVERAGE_STATES, coverage, evaluate_micro_topic_status
from .decisions import MicroTopicDecision, MicroTopicEvaluationContext
from .profiles import compile_semantic_profile, profile_for, profile_quality, resolve_microtopic_profile
from .readiness import check_microtopic_readiness
from .scoring import compute_confidence, score_micro_topic_chunk
from .signals import GENERIC_TERMS, MicroTopicSignalModel, group_policy_satisfied, parse_signal

__all__ = [
    "CANONICAL_COVERAGE_STATES",
    "GENERIC_TERMS",
    "MicroTopicClassificationEngine",
    "MicroTopicDecision",
    "MicroTopicEvaluationContext",
    "MicroTopicSignalModel",
    "catalog",
    "check_microtopic_readiness",
    "classify_micro_topics",
    "compile_semantic_profile",
    "coverage",
    "compute_confidence",
    "evaluate_micro_topic_status",
    "group_policy_satisfied",
    "parse_signal",
    "profile_for",
    "profile_quality",
    "resolve_microtopic_profile",
    "score_micro_topic_chunk",
    "validate_microtopic_coverage",
]
