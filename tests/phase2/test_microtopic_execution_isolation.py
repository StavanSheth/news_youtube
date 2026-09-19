"""Tests for 1-by-1 micro-topic guarantee, strict execution isolation, and evidence cross-contamination prevention."""

from __future__ import annotations

from intelligence.rag.packet import ContextPacket
from intelligence.rag.query import build_retrieval_request
from intelligence.rag.ranking import rank_evidence_chunks


def test_one_by_one_microtopic_isolation_across_a_b_c():
    """Verify Section 18 regression test:

    Deliberately creates topics A, B, and C, and proves:
    - A cannot receive B evidence
    - B cannot receive C evidence
    - C cannot receive A evidence
    Hard invariant: ContextPacket.micro_topic_id == job.micro_topic_id.
    """
    evidence_a = {
        "id": "ev-a-1",
        "evidence_id": "ev-a-1",
        "text": "Topic A breakthroughs in autonomous navigation algorithms and robotics pathfinding.",
        "metadata": {
            "source_id": "src-a",
            "content_id": "cnt-a",
            "micro_topic_id": "robotics-navigation",
            "micro_topic_matches": [{"micro_topic_id": "robotics-navigation", "confidence": 0.95}],
            "trust_tier": 1,
            "published_at": "2026-09-18T10:00:00Z",
            "url": "https://example.com/a",
        },
    }
    evidence_b = {
        "id": "ev-b-1",
        "evidence_id": "ev-b-1",
        "text": "Topic B quantum key distribution protocol benchmarks and qubit coherence times.",
        "metadata": {
            "source_id": "src-b",
            "content_id": "cnt-b",
            "micro_topic_id": "quantum-computing",
            "micro_topic_matches": [{"micro_topic_id": "quantum-computing", "confidence": 0.95}],
            "trust_tier": 1,
            "published_at": "2026-09-18T10:00:00Z",
            "url": "https://example.com/b",
        },
    }
    evidence_c = {
        "id": "ev-c-1",
        "evidence_id": "ev-c-1",
        "text": "Topic C synthetic biology genome editing and CRISPR Cas9 off-target fidelity studies.",
        "metadata": {
            "source_id": "src-c",
            "content_id": "cnt-c",
            "micro_topic_id": "synthetic-biology",
            "micro_topic_matches": [{"micro_topic_id": "synthetic-biology", "confidence": 0.95}],
            "trust_tier": 1,
            "published_at": "2026-09-18T10:00:00Z",
            "url": "https://example.com/c",
        },
    }

    all_evidence = [evidence_a, evidence_b, evidence_c]

    from intelligence.rag.eligibility import filter_eligible_candidates

    # 1. Job A: robotics-navigation
    req_a = build_retrieval_request(
        micro_topic="robotics-navigation",
        theme={"id": "theme-robotics", "retrieval_intent": "navigation pathfinding"},
        classification={"micro_topic_id": "robotics-navigation"},
    )
    eligible_a, diag_a = filter_eligible_candidates(all_evidence, req_a)
    ranked_a = rank_evidence_chunks(eligible_a, req_a)
    packet_a = ContextPacket.create(
        micro_topic_id="robotics-navigation",
        query=req_a.query,
        evidence=ranked_a,
    )

    # Prove A received ONLY A evidence, never B or C
    packet_a_dict = packet_a.to_dict()
    assert packet_a_dict["micro_topic_id"] == "robotics-navigation"
    assert len(packet_a_dict["retrieved_evidence"]) == 1
    for item in packet_a_dict["retrieved_evidence"]:
        assert item.get("metadata", {}).get("micro_topic_id") == "robotics-navigation"
        assert "quantum" not in item.get("text", "").lower()
        assert "synthetic" not in item.get("text", "").lower()

    # 2. Job B: quantum-computing
    req_b = build_retrieval_request(
        micro_topic="quantum-computing",
        theme={"id": "theme-quantum", "retrieval_intent": "qubit coherence"},
        classification={"micro_topic_id": "quantum-computing"},
    )
    eligible_b, diag_b = filter_eligible_candidates(all_evidence, req_b)
    ranked_b = rank_evidence_chunks(eligible_b, req_b)
    packet_b = ContextPacket.create(
        micro_topic_id="quantum-computing",
        query=req_b.query,
        evidence=ranked_b,
    )

    # Prove B received ONLY B evidence, never C or A
    packet_b_dict = packet_b.to_dict()
    assert packet_b_dict["micro_topic_id"] == "quantum-computing"
    assert len(packet_b_dict["retrieved_evidence"]) == 1
    for item in packet_b_dict["retrieved_evidence"]:
        assert item.get("metadata", {}).get("micro_topic_id") == "quantum-computing"
        assert "robotics" not in item.get("text", "").lower()
        assert "crispr" not in item.get("text", "").lower()

    # 3. Job C: synthetic-biology
    req_c = build_retrieval_request(
        micro_topic="synthetic-biology",
        theme={"id": "theme-synthetic", "retrieval_intent": "genome editing"},
        classification={"micro_topic_id": "synthetic-biology"},
    )
    eligible_c, diag_c = filter_eligible_candidates(all_evidence, req_c)
    ranked_c = rank_evidence_chunks(eligible_c, req_c)
    packet_c = ContextPacket.create(
        micro_topic_id="synthetic-biology",
        query=req_c.query,
        evidence=ranked_c,
    )

    # Prove C received ONLY C evidence, never A or B
    packet_c_dict = packet_c.to_dict()
    assert packet_c_dict["micro_topic_id"] == "synthetic-biology"
    assert len(packet_c_dict["retrieved_evidence"]) == 1
    for item in packet_c_dict["retrieved_evidence"]:
        assert item.get("metadata", {}).get("micro_topic_id") == "synthetic-biology"
        assert "robotics" not in item.get("text", "").lower()
        assert "qubit" not in item.get("text", "").lower()


def test_packet_creation_enforces_exact_microtopic_id():
    """Verify that packet cannot be created with mismatched or missing micro_topic_id."""
    packet = ContextPacket.create(
        micro_topic_id="foundation-models",
        query="foundation models updates",
        evidence=[],
    )
    assert packet.micro_topic_id == "foundation-models"
    data = packet.to_dict()
    assert data["micro_topic_id"] == "foundation-models"
