"""Golden dataset evaluation testing classification, isolation, and status resolution."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from intelligence.config import load_config
from intelligence.coverage import resolve_micro_topic_status, CoverageState
from intelligence.microtopics import catalog, classify_micro_topics
from intelligence.rag.eligibility import check_chunk_eligibility
from intelligence.rag.query import RetrievalRequest

ROOT = Path(__file__).parents[1]


def test_golden_dataset_evaluation_and_contracts():
    corpus_path = ROOT / "tests" / "fixtures" / "golden_corpus.json"
    golden_records = json.loads(corpus_path.read_text(encoding="utf-8"))
    assert len(golden_records) >= 20

    config = load_config(ROOT)
    entries = catalog(config.taxonomy, config.topics, config.microtopics, config.microtopic_matrix, config.profile_templates)

    correct_classifications = 0
    total_evaluable = 0

    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)
    cutoff = datetime(2026, 9, 18, 11, 0, 0, tzinfo=UTC)

    for item in golden_records:
        expected_micro = item.get("expected_micro_topic")
        expected_status = item.get("expected_status")

        # 1. Temporal / Future test
        if expected_status == "HARD_REJECT_FUTURE":
            chunk = {
                "id": item["id"],
                "text": item["text"],
                "metadata": {
                    "content_id": item["id"],
                    "source_id": item["source"],
                    "published_at": item["published_at"],
                    "trust_tier": 2,
                    "micro_topic_id": expected_micro,
                    "provenance": {"source_url": item["url"]},
                },
            }
            req = RetrievalRequest(query=item["title"], micro_topic_id=expected_micro, theme_id="theme")
            is_eligible, reason = check_chunk_eligibility(chunk, req, now=now, publication_cutoff=cutoff)
            assert is_eligible is False
            assert "FUTURE" in reason
            continue

        # 2. Irrelevant gardening item
        if expected_status == "NO_RELEVANT_CONTENT":
            matches = classify_micro_topics(item, entries)
            # Should have no high-confidence matching micro-topics
            assert not any(m["classification_score"] > 0.7 for m in matches)
            continue

        # 3. Status test for no-major-update
        if expected_status == "NO_MAJOR_UPDATE":
            eval_data = {"evaluation_status": "EVALUATION_COMPLETE", "evaluated": True}
            assigned = [{"micro_topic": expected_micro, "importance_score": 45, "candidate_count": 2, "relevant_count": 1}]
            status, _ = resolve_micro_topic_status(assigned, eval_data)
            assert status == CoverageState.CHECKED_NO_MAJOR_UPDATE
            continue

        # 4. Status test for insufficient evidence
        if expected_status == "INSUFFICIENT_EVIDENCE":
            eval_data = {"evaluation_status": "EVALUATION_COMPLETE"}
            assigned = [{"micro_topic": expected_micro, "importance_score": 20, "evidence_available": False}]
            status, _ = resolve_micro_topic_status(assigned, eval_data)
            assert status == CoverageState.CHECKED_INSUFFICIENT_EVIDENCE
            continue

        # 5. Adversarial prompt injection item
        if expected_status == "RESISTED":
            continue

        # 6. Normal classified items
        if expected_micro and expected_micro != "unclassified":
            total_evaluable += 1
            matches = classify_micro_topics(item, entries)
            matched_ids = [m["micro_topic"] for m in matches]
            if expected_micro in matched_ids:
                correct_classifications += 1

    accuracy = correct_classifications / max(1, total_evaluable)
    # Target accuracy on golden dataset >= 85%
    assert accuracy >= 0.85
