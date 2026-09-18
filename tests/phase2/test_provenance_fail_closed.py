"""Phase 2C tests for fail-closed provenance validation and citation integrity."""

from __future__ import annotations

from intelligence.validation.provenance import validate_claim_provenance, verify_provenance


def test_material_claim_without_context_packet_fails_closed():
    analysis = {
        "facts": ["Qubit error rate reduced below surface threshold."],
        "claims": [
            {
                "claim_id": "c1",
                "text": "Physical error threshold reached.",
                "claim_type": "FACT",
                "evidence_ids": ["ev-1"],
            }
        ],
    }
    # No context packet provided -> MUST fail closed!
    ok, errors = validate_claim_provenance(analysis, context_packet=None)
    assert ok is False
    assert any("fail-closed" in e.lower() for e in errors)


def test_cited_evidence_id_missing_from_packet_fails():
    analysis = {
        "claims": [
            {
                "claim_id": "c1",
                "text": "Quantum volume doubled.",
                "claim_type": "FACT",
                "evidence_ids": ["ev-phantom"],
            }
        ]
    }
    packet = {
        "evidence_ids": ["ev-actual-1", "ev-actual-2"],
        "retrieved_evidence": [{"id": "ev-actual-1"}, {"id": "ev-actual-2"}],
    }
    ok, errors = validate_claim_provenance(analysis, context_packet=packet)
    assert ok is False
    assert any("not present in context packet" in e or "does not exist" in e for e in errors)


def test_deep_provenance_mismatch_content_id():
    claim = {
        "claim_id": "c1",
        "evidence_ids": ["ev-1"],
        "content_id": "item-claimed",
    }
    packet = {
        "evidence_ids": ["ev-1"],
        "retrieved_evidence": [
            {"id": "ev-1", "metadata": {"content_id": "item-actual", "source_id": "src-1"}}
        ],
    }
    ok, errors = verify_provenance(claim, context_packet=packet)
    assert ok is False
    assert any("Provenance mismatch" in e for e in errors)
