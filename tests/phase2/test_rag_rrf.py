"""Phase 2B tests for Reciprocal Rank Fusion (RRF) formula and determinism."""

from __future__ import annotations

from intelligence.rag.fusion import reciprocal_rank_fusion


def test_rrf_formula_accuracy():
    c1 = {"id": "c1", "text": "Document 1"}
    c2 = {"id": "c2", "text": "Document 2"}

    # List A: c1 at rank 1, c2 at rank 2
    # List B: c2 at rank 1, c1 at rank 2
    list_a = [(c1, 10.0), (c2, 5.0)]
    list_b = [(c2, 0.95), (c1, 0.85)]

    k = 60
    fused = reciprocal_rank_fusion([list_a, list_b], k=k, top_k=2)

    # Both items have identical RRF: 1/(60+1) + 1/(60+2) = 1/61 + 1/62 = 0.016393 + 0.016129 = 0.032522
    expected_score = round(1.0 / 61.0 + 1.0 / 62.0, 6)
    assert len(fused) == 2
    assert fused[0][1] == expected_score
    assert fused[1][1] == expected_score


def test_rrf_determinism():
    c1 = {"id": "c1", "text": "Document 1"}
    c2 = {"id": "c2", "text": "Document 2"}
    c3 = {"id": "c3", "text": "Document 3"}

    list_a = [(c1, 5.0), (c2, 3.0), (c3, 1.0)]
    list_b = [(c1, 0.9), (c3, 0.7), (c2, 0.5)]

    run1 = reciprocal_rank_fusion([list_a, list_b], k=60, top_k=3)
    run2 = reciprocal_rank_fusion([list_a, list_b], k=60, top_k=3)

    assert [c[0]["id"] for c in run1] == [c[0]["id"] for c in run2]
    assert [score for _, score in run1] == [score for _, score in run2]
    # c1 is rank 1 in both, so it must be top
    assert run1[0][0]["id"] == "c1"
