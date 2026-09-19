"""Tests for observability metrics registry, source execution tracking, and aggregated rates."""

from __future__ import annotations

import pytest

from intelligence.observability.metrics import MetricsRegistry


def test_metrics_registry_source_execution_and_aggregated_rates():
    reg = MetricsRegistry()

    # Record 3 successful executions
    reg.record_source_execution(
        source_id="rss-reuters",
        provider="rss",
        latency_ms=120.0,
        items_seen=10,
        items_valid=9,
        items_rejected=1,
        collection_success=True,
        schema_valid=True,
        content_extractable=True,
        rag_items_ingested=9,
        rag_items_rejected=1,
        retry_count=0,
    )
    reg.record_source_execution(
        source_id="newsapi-top",
        provider="news_api",
        latency_ms=250.0,
        items_seen=20,
        items_valid=20,
        items_rejected=0,
        collection_success=True,
        schema_valid=True,
        content_extractable=True,
        rag_items_ingested=20,
        rag_items_rejected=0,
        retry_count=1,
    )

    # Record 1 failed execution
    reg.record_source_execution(
        source_id="yt-broken",
        provider="youtube",
        latency_ms=80.0,
        items_seen=0,
        items_valid=0,
        items_rejected=0,
        collection_success=False,
        schema_valid=False,
        content_extractable=False,
        failure_code="CHANNEL_NOT_FOUND",
        retry_count=2,
    )

    rates = reg.compute_aggregated_rates()
    assert rates["source_success_rate"] == pytest.approx(66.67, abs=0.1)
    assert rates["source_failure_rate"] == pytest.approx(33.33, abs=0.1)
    assert rates["RAG_ingestion_rate"] == pytest.approx(96.67, abs=0.1)
    assert rates["freshness_rate"] == pytest.approx(96.67, abs=0.1)
    assert rates["microtopic_coverage"] == 100.0

    snap = reg.snapshot()
    assert snap["counters"]["items_seen_total"] == 30
    assert snap["counters"]["items_valid_total"] == 29
    assert snap["counters"]["items_rejected_total"] == 1
    assert snap["counters"]["rag_items_ingested_total"] == 29
    assert snap["counters"]["retries_total"] == 3
