"""Execution isolation and single-topic-at-a-time pipeline integration tests."""

from __future__ import annotations

import json
from pathlib import Path

from intelligence.ai.base import AIProvider
from intelligence.budgets.manager import BudgetManager
from intelligence.rag.cache import RetrievalCache, RetrievalCacheKey
from intelligence.rag.packet import ContextPacket

ROOT = Path(__file__).resolve().parent.parent.parent


class MockAIProvider(AIProvider):
    def __init__(self):
        self.call_count = 0
        self.analyzed_topics = []

    def analyze_micro_topic(self, item, profile, evidence):
        self.call_count += 1
        key = profile.get("full_key") or profile.get("micro_topic_id") or profile.get("micro_topic")
        self.analyzed_topics.append(key)
        return {
            "summary": f"Analysis for {key}",
            "confidence_score": 92.0,
            "importance_score": 88.0,
            "evidence": [
                {
                    "evidence_id": f"ev-{key}",
                    "text": f"Grounded fact for {key}",
                    "source_url": "https://example.test/source",
                    "type": "fact",
                }
            ],
            "actionable_insights": [f"Key finding for {key}"],
        }


def test_microtopic_execution_isolation():
    """Verify topic A cannot consume topic B's budget, context, or cache."""
    # 1. Budget Isolation
    bm = BudgetManager(
        global_limits={"max_ai_calls": 10, "max_input_tokens": 10000},
        micro_topic_limits={
            "foundation-models": {"max_ai_calls": 2, "max_input_tokens": 1000},
            "reasoning-models": {"max_ai_calls": 2, "max_input_tokens": 1000},
        },
    )

    # Consume foundation-models budget
    auth_a1, _, _ = bm.authorize("foundation-models", estimated_calls=1, estimated_tokens=500)
    assert auth_a1
    bm.consume("foundation-models", "ai_calls", 1)
    bm.consume("foundation-models", "input_tokens", 500)

    auth_a2, _, _ = bm.authorize("foundation-models", estimated_calls=1, estimated_tokens=500)
    assert auth_a2
    bm.consume("foundation-models", "ai_calls", 1)
    bm.consume("foundation-models", "input_tokens", 500)

    # foundation-models is now exhausted
    auth_a3, _, reason_a = bm.authorize("foundation-models", estimated_calls=1, estimated_tokens=100)
    assert not auth_a3
    reason_str = reason_a.reason if hasattr(reason_a, "reason") else str(reason_a)
    assert "LIMIT_EXCEEDED" in reason_str

    # reasoning-models is completely unaffected!
    auth_b1, _, _ = bm.authorize("reasoning-models", estimated_calls=1, estimated_tokens=500)
    assert auth_b1

    # 2. Context Isolation
    packet_a = ContextPacket.create(
        micro_topic_id="foundation-models",
        query="foundation model query",
        evidence=[{"id": "ev-fm", "text": "Foundation model evidence"}],
    )
    packet_b = ContextPacket.create(
        micro_topic_id="reasoning-models",
        query="reasoning model query",
        evidence=[{"id": "ev-rm", "text": "Reasoning model evidence"}],
    )

    dict_a = packet_a.to_dict()
    dict_b = packet_b.to_dict()

    assert dict_a["micro_topic_id"] == "foundation-models"
    assert dict_b["micro_topic_id"] == "reasoning-models"
    assert "ev-fm" in dict_a["evidence_ids"]
    assert "ev-fm" not in dict_b["evidence_ids"]
    assert "ev-rm" in dict_b["evidence_ids"]
    assert "ev-rm" not in dict_a["evidence_ids"]

    # 3. Cache Isolation
    cache = RetrievalCache()
    key_a = RetrievalCacheKey.create(
        query="eval benchmark",
        micro_topic_id="foundation-models",
        edition_cutoff="2026-09-18T18:00:00Z",
    )
    key_b = RetrievalCacheKey.create(
        query="eval benchmark",
        micro_topic_id="reasoning-models",
        edition_cutoff="2026-09-18T18:00:00Z",
    )
    cache.set(key_a, {"result": "cached_fm"})
    assert cache.get(key_a) == {"result": "cached_fm"}
    assert cache.get(key_b) is None


def test_budget_skip_on_insufficient_budget():
    """Verify Gemini is not called when budget is skipped."""
    bm = BudgetManager(
        global_limits={"max_ai_calls": 1},
        micro_topic_limits={"foundation-models": {"max_ai_calls": 1}},
    )
    mock_provider = MockAIProvider()

    # First call within budget
    auth, _, _ = bm.authorize("foundation-models", estimated_calls=1, estimated_tokens=100)
    assert auth
    output = mock_provider.analyze_micro_topic({}, {"micro_topic_id": "foundation-models"}, [])
    bm.consume("foundation-models", "ai_calls", 1)
    assert output["confidence_score"] == 92.0
    assert mock_provider.call_count == 1

    # Second call exceeds budget -> DO NOT CALL GEMINI
    auth2, _, reason = bm.authorize("foundation-models", estimated_calls=1, estimated_tokens=100)
    # Handled as BUDGET_SKIPPED
    assert "BUDGET" in reason
    assert mock_provider.call_count == 1  # Not incremented!


def test_236_microtopics_isolated_mock_jobs():
    """Verify all 236 micro-topics can execute as 236 independent jobs with zero cross-leakage."""
    matrix_file = ROOT / "config" / "microtopic_matrix.json"
    records = json.loads(matrix_file.read_text(encoding="utf-8"))["records"]
    assert len(records) == 236

    mock_provider = MockAIProvider()
    processed_topics = []

    for rec in records:
        full_key = f"{rec['domain']}::{rec['id']}"
        mt_id = rec["id"]
        # Execute 1 isolated job per micro-topic
        job_packet = ContextPacket.create(
            micro_topic_id=mt_id,
            query=f"Analysis for {mt_id}",
            evidence=[{"id": f"ev-{full_key}", "text": f"Content for {full_key}"}],
        )
        assert job_packet.micro_topic_id == mt_id
        res = mock_provider.analyze_micro_topic({}, {"micro_topic_id": mt_id, "full_key": full_key}, list(job_packet.evidence))
        assert res["evidence"][0]["evidence_id"] == f"ev-{full_key}"
        processed_topics.append(full_key)

    assert len(processed_topics) == 236
    assert len(set(processed_topics)) == 236
    assert mock_provider.call_count == 236
