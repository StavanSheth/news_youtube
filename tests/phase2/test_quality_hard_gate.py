"""Phase 2C tests for honest quality scorecard and hard failure gate capping."""

from __future__ import annotations

from intelligence.quality import evaluate_output


def test_uncited_claims_hard_gate_caps_score_at_59():
    story = {
        "id": "item-1",
        "url": "https://example.test/item1",
        "source": "physics_today",
        "importance_score": 90,
        "confidence_score": 85,
        "micro_topics": [{"micro_topic": "quantum-hardware"}],
        "theme": "quantum-physics",
        "retrieved_evidence": [{"text": "valid qubit text"}],
        "analysis": {
            "facts": ["Surface code qubit achieved error suppression."],
            "actionable_insights": ["Engineering teams should deploy error mitigation codes."],
            "evidence": [],  # UNCITED!
        },
    }
    result = evaluate_output(
        stories=[story],
        markdown="# Title\n\nContent",
        html="<html><body><h1>Title</h1><p>Content</p></body></html>",
        coverage=[{"status": "UPDATE"}],
        source_health={"physics_today": {"status": "HEALTHY"}},
    )

    # Must fail gate and cap score at <= 59
    assert result["passed"] is False
    assert result["status"] == "QUALITY_REVIEW_REQUIRED"
    assert result["checks"]["claims_cited"] is False
    assert result["scores"]["overall"] <= 59


def test_broken_html_hard_gate_caps_score_at_59():
    story = {
        "id": "item-2",
        "url": "https://example.test/item2",
        "source": "wire",
        "importance_score": 80,
        "confidence_score": 80,
        "micro_topics": [{"micro_topic": "ai"}],
        "theme": "ai-theme",
        "retrieved_evidence": [{"text": "evidence"}],
        "analysis": {
            "facts": ["Fact text"],
            "actionable_insights": ["Action text here"],
            "evidence": [{"type": "fact", "text": "Fact text", "source_url": "https://example.test/item2"}],
        },
    }
    # Unbalanced HTML tag <p> without </p>
    result = evaluate_output(
        stories=[story],
        markdown="# Title\n\nContent",
        html="<html><body><p>unclosed tag</body></html>",
        coverage=[{"status": "UPDATE"}],
        source_health={"wire": {"status": "HEALTHY"}},
    )
    assert result["passed"] is False
    assert result["checks"]["html_balanced"] is False
    assert result["scores"]["overall"] <= 59


def test_perfect_story_calculates_full_honest_score():
    story = {
        "id": "item-ok",
        "url": "https://example.test/ok",
        "source": "valid_source",
        "importance_score": 85,
        "confidence_score": 90,
        "micro_topics": [{"micro_topic": "quantum-hardware"}],
        "theme": "quantum-hardware",
        "retrieved_evidence": [{"text": "clean evidence text"}],
        "analysis": {
            "facts": ["Deterministic qubit fabrication improves yield 20%."],
            "actionable_insights": ["Adopt dual-junction lithography for 2027 roadmaps."],
            "evidence": [
                {
                    "type": "fact",
                    "text": "Deterministic qubit fabrication improves yield 20%.",
                    "source_url": "https://example.test/ok",
                }
            ],
        },
    }
    result = evaluate_output(
        stories=[story],
        markdown="# Quantum Digest\n\nFabrication advances.",
        html="<html><body><h1>Quantum Digest</h1><p>Fabrication advances.</p></body></html>",
        coverage=[{"status": "UPDATE"}],
        source_health={"valid_source": {"status": "HEALTHY"}},
    )
    assert result["passed"] is True
    assert result["scores"]["overall"] >= 95
    assert result["scores"]["provenance_integrity"] == 100
    assert result["scores"]["microtopic_accuracy"] == 100
