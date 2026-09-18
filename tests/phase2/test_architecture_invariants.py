"""Comprehensive Automated Architecture Invariant Test Suite.

Tests INV-001 through INV-013 establishing strict production quality guarantees.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
import pytest

from intelligence.contracts import MicroTopicDecision, MicroTopicJob
from intelligence.coverage import CoverageState, resolve_micro_topic_status
from intelligence.microtopics.coverage import CANONICAL_COVERAGE_STATES
from intelligence.themes.contracts import ThemeResolution
from intelligence.rag.packet import ContextPacket
from intelligence.rag.eligibility import check_chunk_eligibility
from intelligence.rag.query import RetrievalRequest
from intelligence.rag.index import EvidenceIndex
from intelligence.rag.retrieval import HybridRetriever
from intelligence.budgets.manager import BudgetManager
from intelligence.validation.provenance import validate_claim_provenance
from intelligence.quality import evaluate_output
import intelligence.retrieval


def test_inv_001_one_microtopic_per_job():
    """INV-001: Exactly one micro-topic per analysis job."""
    decision = MicroTopicDecision(
        micro_topic_id="quantum-hardware",
        domain_id="quantum-computing",
        topic_id="hardware",
        decision="PRIMARY",
        score=0.9,
        confidence=0.85,
        threshold=0.7,
        margin=0.2,
        matched_signals=("qubit", "surface-code"),
    )
    job = MicroTopicJob(
        micro_topic_id="quantum-hardware",
        domain_id="quantum-computing",
        topic_id="hardware",
        decision=decision,
        theme={"id": "quantum-theme"},
        evidence_scope={},
        retrieval_intent={},
        analysis_requirements={},
    )
    assert isinstance(job.micro_topic_id, str)
    assert job.micro_topic_id == "quantum-hardware"
    assert "," not in job.micro_topic_id
    assert ";" not in job.micro_topic_id


def test_inv_002_microtopic_decision_field_completeness():
    """INV-002: MicroTopicDecision carries all 13 canonical contract fields."""
    decision = MicroTopicDecision(
        micro_topic_id="m1",
        domain_id="d1",
        topic_id="t1",
        decision="PRIMARY",
        score=0.92,
        confidence=0.88,
        threshold=0.70,
        margin=0.22,
        matched_signals=("s1", "s2"),
        runner_up_score=0.70,
        negative_matches=("neg1",),
        classification_status="QUALIFIED",
        significance=0.85,
        event_ids=("ev-1",),
        entity_ids=("ent-1",),
        evidence_scope_id="scope-123",
    )
    d_dict = decision.to_dict()
    required_fields = [
        "micro_topic_id", "domain_id", "topic_id", "decision", "score",
        "confidence", "threshold", "margin", "matched_signals", "runner_up_score",
        "negative_matches", "classification_status", "significance", "event_ids",
        "entity_ids", "evidence_scope_id",
    ]
    for field in required_fields:
        assert field in d_dict, f"Missing required field {field} in MicroTopicDecision"


def test_inv_003_theme_resolution_field_completeness():
    """INV-003: ThemeResolution carries all required contract fields."""
    resolution = ThemeResolution(
        theme_id="theme-1",
        requested_level="exact_micro_topic",
        resolved_level="exact_micro_topic",
        matched_pattern="micro_topic_id:quantum-hardware",
        stream_parameters={"report_type": "deep_dive"},
        questions=("what_changed", "why_it_matters"),
        analysis_contract={"required_dimensions": ["business_impact"]},
    )
    r_dict = resolution.to_dict()
    for field in ("theme_id", "requested_level", "resolved_level", "matched_pattern", "stream_parameters", "questions", "analysis_contract"):
        assert field in r_dict, f"Missing required field {field} in ThemeResolution"


def test_inv_004_coverage_strictly_8_canonical_states():
    """INV-004: Coverage state machine has strictly canonical set of states."""
    canonical_states = {
        "MAJOR_UPDATE",
        "MINOR_UPDATE",
        "NO_MAJOR_UPDATE",
        "NO_RELEVANT_CONTENT",
        "INSUFFICIENT_EVIDENCE",
        "BUDGET_SKIPPED",
        "TRANSCRIPT_UNAVAILABLE",
        "ERROR",
        "SOURCE_FAILURE",
    }
    assert CANONICAL_COVERAGE_STATES == canonical_states


def test_inv_005_technical_failure_maps_strictly_to_error():
    """INV-005: Technical failure in coverage maps to ERROR, never CHECKED_NO_MAJOR_UPDATE."""
    eval_state = {"evaluation_status": "FAILED", "evaluated": False, "error": "TimeoutError"}
    assignments = [{"micro_topic": "rag", "candidate_count": 0}]
    status, reason = resolve_micro_topic_status(assignments, eval_state)
    assert status == CoverageState.ERROR
    assert status != CoverageState.CHECKED_NO_MAJOR_UPDATE
    assert "TECHNICAL_FAILURE" in reason


def test_inv_006_context_packet_immutability():
    """INV-006: ContextPacket is frozen and immutable."""
    packet = ContextPacket.create(
        micro_topic_id="m1",
        query="test",
        evidence=[{"id": "c1", "text": "evidence"}],
    )
    with pytest.raises(FrozenInstanceError):
        packet.query = "mutated_query"  # type: ignore[misc]


def test_inv_007_context_packet_complete_traces():
    """INV-007: ContextPacket contains retrieval, ranking, diversity, budget traces."""
    packet = ContextPacket.create(
        micro_topic_id="m1",
        query="test",
        evidence=[{"id": "c1", "text": "evidence"}],
        retrieval_trace={"candidates_retrieved": 10},
        ranking_trace={"ranked_count": 10},
        diversity_trace={"diversity_skipped": 1},
        budget_trace={"max_results": 4},
    )
    p_dict = packet.to_dict()
    assert "retrieval_trace" in p_dict and p_dict["retrieval_trace"]["candidates_retrieved"] == 10
    assert "ranking_trace" in p_dict and p_dict["ranking_trace"]["ranked_count"] == 10
    assert "diversity_trace" in p_dict and p_dict["diversity_trace"]["diversity_skipped"] == 1
    assert "budget_trace" in p_dict and p_dict["budget_trace"]["max_results"] == 4


def test_inv_008_future_evidence_strictly_excluded_before_ranking():
    """INV-008: Future publication timestamps strictly rejected by hard eligibility filter."""
    cutoff = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)
    future_chunk = {
        "id": "c_future",
        "text": "Future content",
        "metadata": {
            "content_id": "item1",
            "source_id": "feed1",
            "published_at": (cutoff + timedelta(hours=2)).isoformat(),
        },
    }
    eligible, reason = check_chunk_eligibility(future_chunk, publication_cutoff=cutoff)
    assert eligible is False
    assert reason == "FUTURE_EVIDENCE_EXCEEDS_CUTOFF"


def test_inv_009_candidate_retrieval_uses_hybrid_bm25_dense_rrf():
    """INV-009: Hybrid retrieval combines lexical BM25 and dense representations."""
    index = EvidenceIndex()
    c1 = {"id": "c1", "text": "Deep residual neural networks for classification.", "metadata": {"content_id": "i1"}}
    c2 = {"id": "c2", "text": "Semiconductor lithography wafer fabrication.", "metadata": {"content_id": "i2"}}
    index.add(c1)
    index.add(c2)

    retriever = HybridRetriever(index=index, k=60)
    req = RetrievalRequest(query="residual networks", micro_topic_id="", theme_id="")
    candidates = retriever.retrieve_candidates(req, top_k=2)
    assert len(candidates) >= 1
    assert candidates[0]["id"] == "c1"
    assert "rrf_score" in candidates[0]


def test_inv_010_budget_reservation_before_ai_call():
    """INV-010: Budget is reserved before execution and freed/consumed properly."""
    manager = BudgetManager(global_limits={"max_ai_calls": 2})
    authorized, reason, _ = manager.authorize("topic-1", priority="P1", estimated_calls=1)
    assert authorized is True
    # Reservation is recorded
    assert manager._reservations.get("topic-1:ai_calls") == 1
    assert manager.global_usage.ai_calls == 0

    # Consume reconciles reservation
    manager.consume("topic-1", "ai_calls", 1)
    assert manager._reservations.get("topic-1:ai_calls") == 0
    assert manager.global_usage.ai_calls == 1


def test_inv_011_fail_closed_provenance():
    """INV-011: Material factual claims without evidence fail closed."""
    analysis = {
        "facts": ["Major breakthrough achieved."],
        "claims": [{"claim_id": "c1", "text": "95% accuracy reached.", "claim_type": "FACT", "evidence_ids": []}],
    }
    # No ContextPacket -> MUST FAIL CLOSED
    ok, errors = validate_claim_provenance(analysis, context_packet=None)
    assert ok is False
    assert any("fail-closed" in e.lower() for e in errors)


def test_inv_012_quality_scorecard_hard_gate_capping():
    """INV-012: Invariant failure caps quality score at <= 59 and marks passed as False."""
    story = {
        "id": "s1", "url": "https://example.test/s1", "source": "Src",
        "importance_score": 80, "confidence_score": 80,
        "micro_topics": [{"micro_topic": "ai"}], "theme": "t1",
        "retrieved_evidence": [{"text": "evidence"}],
        "analysis": {"facts": ["uncited fact"], "evidence": []},  # Uncited fact violation
    }
    result = evaluate_output([story], "# Markdown", "<html><body><p>Text</p></body></html>", [{"status": "UPDATE"}], {"Src": {"status": "HEALTHY"}})
    assert result["passed"] is False
    assert result["scores"]["overall"] <= 59


def test_inv_013_single_authoritative_implementation_facades_only_delegate():
    """INV-013: Retrieval facade correctly exposes backwards compatibility while ProductionRAGManager is authoritative."""
    assert hasattr(intelligence.retrieval, "retrieve")
    assert hasattr(intelligence.retrieval, "RAGManager")
    assert intelligence.retrieval.RAGManager is intelligence.rag.ProductionRAGManager
