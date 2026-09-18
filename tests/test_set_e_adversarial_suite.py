"""Authoritative Set E Phase 2.1 Adversarial Test Suite.

Tests A through J verifying strict micro-topic isolation, parent topic protection,
negative signal filtering, publication cutoff / future data protection, budget pre-authorization,
retrieval error handling, empty AI rejection, provenance integrity, diversity enforcement,
and theme fallback observability.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from intelligence.budgets.manager import BudgetManager
from intelligence.coverage import CoverageState, resolve_micro_topic_status
from intelligence.manager import MicroTopicManager
from intelligence.microtopics import MicroTopicClassificationEngine, score_micro_topic_chunk
from intelligence.rag.corpus import RepositoryEvidenceCorpus
from intelligence.rag.diversity import apply_diversity_filtering
from intelligence.rag.eligibility import check_chunk_eligibility
from intelligence.rag.manager import ProductionRAGManager
from intelligence.statuses import IntelligenceStatus
from intelligence.themes import select_theme
from intelligence.validation import validate_analysis, verify_provenance


class MockTrackingProvider:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, int]] = []
        self.response = response or {
            "importance_score": 80,
            "confidence_score": 85,
            "facts": ["Verified advancement in semiconductor manufacturing."],
            "summary": "TSMC expanded 2nm wafer capacity significantly.",
            "claims": [{"claim_id": "cl-1", "text": "TSMC expanded capacity", "claim_type": "FACT", "evidence_ids": ["c1:0"]}],
        }

    def analyze_micro_topic(self, item: dict[str, Any], profile: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
        micro_topic = profile.get("micro_topic_id") or profile.get("micro_topic", "")
        self.calls.append((micro_topic, len(evidence)))
        return self.response


# --- TEST A: Cross micro-topic contamination ---
def test_a_cross_microtopic_contamination():
    """AI analyzing Topic A must never receive evidence retrieved for Topic B."""
    corpus = RepositoryEvidenceCorpus()

    semi_item = {
        "id": "item-semi",
        "title": "Semiconductor Fab Expansion",
        "text": "Foundry increases 2nm wafer fab production capacity in Taiwan.",
        "source": "SemiNews",
        "url": "https://semi.test/fab",
        "kind": "news",
        "published_at": "2026-09-18T08:00:00+00:00",
    }
    cyber_item = {
        "id": "item-cyber",
        "title": "Cloud Firewall Exploit",
        "text": "Zero-day vulnerability discovered in firewall firmware allowing remote code execution.",
        "source": "CyberSecWire",
        "url": "https://cyber.test/vuln",
        "kind": "news",
        "published_at": "2026-09-18T08:00:00+00:00",
    }

    corpus.add_item(semi_item)
    corpus.add_item(cyber_item)

    provider = MockTrackingProvider()
    themes = [
        {"id": "semi-theme", "domain": "semiconductors", "micro_topic": "fabs", "questions": ["what_changed"]},
        {"id": "cyber-theme", "domain": "cybersecurity", "micro_topic": "vulnerabilities", "questions": ["what_changed"]},
    ]
    settings = {"retrieval_top_k": 4, "max_retrieved_context_chars": 5000}
    retriever = ProductionRAGManager(settings, corpus=corpus)
    manager = MicroTopicManager(provider, themes, settings, retriever=retriever)

    classifications = [
        {
            "domain": "semiconductors",
            "topic": "Manufacturing",
            "micro_topic": "fabs",
            "micro_topic_id": "fabs",
            "signals": ["foundry", "wafer fab", "2nm"],
        }
    ]

    results = manager.analyze(semi_item, classifications)
    assert len(results) == 1
    evidence_texts = [chunk["text"] for chunk in results[0]["evidence"]]
    assert all("firewall" not in t.lower() for t in evidence_texts)
    assert all("vulnerability" not in t.lower() for t in evidence_texts)
    assert any("foundry" in t.lower() or "wafer" in t.lower() for t in evidence_texts)


# --- TEST B: Generic parent topic leakage ---
def test_b_generic_parent_topic_leakage():
    """Article on AI image generation must be rejected for AI cybersecurity."""
    engine = MicroTopicClassificationEngine()
    profile = {
        "domain": "artificial-intelligence",
        "topic": "AI",
        "micro_topic": "ai-cybersecurity",
        "micro_topic_id": "ai-cybersecurity",
        "positive_signals": ["cyberattack", "vulnerability", "model inversion", "prompt injection", "adversarial attack"],
        "distractors": ["image generation", "diffusion", "art", "creative"],
        "classification_threshold": 0.6,
    }
    item = {
        "title": "New Diffusion Model Generates Photorealistic Art",
        "text": "Researchers released a new text-to-image diffusion model for creative digital art generation.",
    }
    decisions = engine.classify(item, [profile])
    # The micro-topic must be completely rejected (either omitted or flagged as REJECTED)
    assert not any(d.micro_topic_id == "ai-cybersecurity" and d.decision == "PRIMARY" for d in decisions)


# --- TEST C: Negative signal filtering ---
def test_c_negative_signal_filtering():
    """Article combining positive term 'bank' with negative term 'football' must be rejected."""
    profile = {
        "domain": "finance",
        "topic": "Banking",
        "micro_topic": "commercial-banking",
        "positive_signals": ["bank", "interest rates", "lending"],
        "negative_signals": ["football", "stadium", "sports", "sponsorship"],
        "distractors": ["championship"],
        "classification_threshold": 0.5,
    }
    chunk_text = "The commercial bank announced a major football stadium sponsorship deal for the upcoming league championship."
    match = score_micro_topic_chunk(chunk_text, profile)
    # The negative signals must penalize or reject the chunk
    assert match["relevant"] is False or match["score"] < 0.5
    assert len(match.get("negative_signals", [])) > 0


# --- TEST D: Future article rejection ---
def test_d_future_article_cutoff_rejection():
    """Evidence published after the authoritative publication cutoff must be rejected."""
    cutoff = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)
    future_chunk = {
        "id": "future-chunk-1",
        "text": "Future financial statement released post edition.",
        "metadata": {
            "content_id": "future-doc",
            "source_id": "future-source",
            "published_at": "2026-09-18T16:00:00+00:00",  # 4 hours after cutoff
            "provenance": {"source_url": "https://future.test/doc"},
        },
    }
    eligible, reason = check_chunk_eligibility(future_chunk, publication_cutoff=cutoff)
    assert eligible is False
    assert "FUTURE" in reason


# --- TEST E: Budget exhaustion skips AI execution ---
def test_e_budget_exhaustion_skips_ai():
    """When budget is exhausted, pre-authorization fails with BUDGET_SKIPPED and AI is not called."""
    budget = BudgetManager({
        "edition_max_ai_calls": 0,  # Zero calls allowed
        "max_ai_calls_per_micro_topic": 0,
    })
    provider = MockTrackingProvider()
    settings = {"retrieval_top_k": 2}
    themes = [{"id": "t-1", "domain": "all", "micro_topic": "any", "questions": ["what_changed"]}]
    manager = MicroTopicManager(provider, themes, settings, budget=budget)

    item = {"id": "item-1", "source": "Test", "title": "Test Item", "text": "Relevant test content."}
    classifications = [{"domain": "tech", "topic": "Tech", "micro_topic": "ai", "micro_topic_id": "ai"}]

    results = manager.analyze(item, classifications)
    assert len(results) == 1
    res = results[0]
    assert res["analysis_status"] == "BUDGET_SKIPPED"
    assert res["budget_skipped"] is True
    assert len(provider.calls) == 0  # Provider must NEVER be called


# --- TEST F: Retrieval failure does not report NO_MAJOR_UPDATE ---
def test_f_retrieval_failure_reports_error():
    """A technical retrieval failure must resolve to ERROR/RETRIEVAL_FAILURE, never NO_MAJOR_UPDATE."""
    assignments = [
        {
            "domain": "security",
            "micro_topic": "zero-day",
            "retrieval_status": IntelligenceStatus.RETRIEVAL_FAILURE.value,
        }
    ]
    evaluation = {"evaluation_status": "EVALUATION_COMPLETE", "evaluated": True}
    status, reason = resolve_micro_topic_status(assignments, evaluation)
    assert status == CoverageState.ERROR
    assert reason == "RETRIEVAL_FAILURE"
    assert status != CoverageState.CHECKED_NO_MAJOR_UPDATE


# --- TEST G: Empty AI output fails validation ---
def test_g_empty_ai_output_fails_validation():
    """Empty or None AI output must fail validation with ANALYSIS_FAILURE and be unpublishable."""
    job = {
        "theme": {"id": "test-theme", "questions": ["what_changed"]},
        "classification": {"micro_topic_id": "ai", "domain": "tech"},
    }
    packet = {"evidence_ids": ["ev-1"]}

    # Case 1: None payload
    result_none = validate_analysis(None, job, packet)  # type: ignore[arg-type]
    assert result_none.is_publishable is False
    assert result_none.validation_status == "INVALID"

    # Case 2: Empty dict payload
    result_empty = validate_analysis({}, job, packet)
    assert result_empty.is_publishable is False
    assert result_empty.validation_status == "INVALID"


# --- TEST H: Provenance mismatch detected ---
def test_h_provenance_mismatch_detected():
    """Altered evidence_id or mismatched source_id must trigger provenance verification failure."""
    context_packet = {
        "evidence_ids": ["ev-1"],
        "retrieved_evidence": [
            {
                "id": "ev-1",
                "metadata": {
                    "evidence_id": "ev-1",
                    "content_id": "content-100",
                    "source_id": "source-alpha",
                },
            }
        ],
    }

    # Claim referencing non-existent evidence_id
    mismatched_claim = {
        "claim_id": "cl-1",
        "text": "Claim citing wrong evidence",
        "evidence_ids": ["ev-999_wrong"],
        "content_id": "content-100",
        "source_id": "source-alpha",
    }
    ok, errors = verify_provenance(mismatched_claim, context_packet)
    assert ok is False
    assert any("does not exist in context packet" in err for err in errors)

    # Claim referencing correct evidence_id but mismatched source_id
    tampered_source_claim = {
        "claim_id": "cl-2",
        "text": "Claim citing tampered source",
        "evidence_ids": ["ev-1"],
        "content_id": "content-100",
        "source_id": "source-impostor",
    }
    ok2, errors2 = verify_provenance(tampered_source_claim, context_packet)
    assert ok2 is False
    assert any("Provenance mismatch" in err for err in errors2)


# --- TEST I: Hard diversity caps cannot be bypassed ---
def test_i_diversity_cap_cannot_be_bypassed():
    """Hard source cap must remain strictly hard even with surplus candidates."""
    candidates = []
    # 10 chunks from source-dominant
    for i in range(10):
        candidates.append({
            "id": f"chunk-dom-{i}",
            "text": f"Dominant source chunk {i}",
            "score": 0.95 - (i * 0.01),
            "metadata": {"source_id": "source-dominant", "url": "https://dominant.test/a"},
        })
    # 3 chunks from diverse sources
    for i, s in enumerate(["source-b", "source-c", "source-d"]):
        candidates.append({
            "id": f"chunk-div-{i}",
            "text": f"Diverse source chunk {i}",
            "score": 0.80,
            "metadata": {"source_id": s, "url": f"https://{s}.test/a"},
        })

    selected, diag = apply_diversity_filtering(
        candidates,
        max_per_source=2,
        target_count=6,
    )
    dom_count = sum(1 for c in selected if c["metadata"]["source_id"] == "source-dominant")
    assert dom_count <= 2
    # Even if total selected is 5 (2 dominant + 3 others), it must not include a 3rd dominant chunk
    assert len(selected) <= 5
    assert diag["diversity_skipped"] > 0


# --- TEST J: Theme fallback observability ---
def test_j_theme_fallback_observability():
    """When exact micro-topic theme is absent, fallback must be observable with origin and reason."""
    themes = [
        {
            "id": "global-fallback-theme",
            "domain": "all",
            "micro_topic": "any",
            "questions": ["what_changed"],
        }
    ]
    classification = {
        "domain": "quantum-computing",
        "topic": "Quantum",
        "micro_topic": "qubit-error-correction",
        "micro_topic_id": "qubit-error-correction",
    }
    item = {"title": "Quantum Error Correction", "text": "Surface code qubit error threshold reached."}

    theme = select_theme(classification, themes, item)
    assert theme["fallback_used"] is True
    assert theme["fallback_reason"] != ""
    assert theme["theme_resolution"] in {"DOMAIN_FALLBACK", "GLOBAL_FALLBACK", "CONTROLLED_FALLBACK"}
