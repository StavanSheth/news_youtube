"""Evaluation harness for RAG hybrid retrieval measuring MRR, Precision@K, Recall@K, and Hit Rate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from intelligence.rag.index import EvidenceIndex
from intelligence.rag.query import RetrievalRequest
from intelligence.rag.retrieval import HybridRetriever


def run_retrieval_evaluation(benchmark_file: Path | None = None) -> dict[str, Any]:
    if benchmark_file is None:
        benchmark_file = Path(__file__).parent / "golden_retrieval.json"

    data = json.loads(benchmark_file.read_text(encoding="utf-8"))
    corpus = data["corpus"]
    queries = data["queries"]

    # Index corpus into EvidenceIndex
    index = EvidenceIndex()
    for doc in corpus:
        index.add(doc)

    retriever = HybridRetriever(index=index)

    reciprocal_ranks: list[float] = []
    precisions_at_k: list[float] = []
    recalls_at_k: list[float] = []
    hits_at_k: list[int] = []

    k = 3

    for q in queries:
        query_text = q["query"]
        relevant_doc_ids = set(q["relevant_docs"])
        micro_topic_id = q.get("micro_topic_id", "")

        request = RetrievalRequest(
            query=query_text,
            micro_topic_id=micro_topic_id,
            theme_id="eval-theme",
            max_results=k,
        )

        results = retriever.retrieve_candidates(request, top_k=k)
        retrieved_ids = [doc.get("id") for doc in results]

        # Calculate Reciprocal Rank
        rr = 0.0
        for rank_idx, doc_id in enumerate(retrieved_ids, start=1):
            if doc_id in relevant_doc_ids:
                rr = 1.0 / rank_idx
                break
        reciprocal_ranks.append(rr)

        # Calculate Precision@K, Recall@K, Hit Rate
        hits = len(relevant_doc_ids.intersection(retrieved_ids))
        precision = hits / k if k > 0 else 0.0
        recall = hits / len(relevant_doc_ids) if relevant_doc_ids else 0.0
        hit = 1 if hits > 0 else 0

        precisions_at_k.append(precision)
        recalls_at_k.append(recall)
        hits_at_k.append(hit)

    mrr = round(sum(reciprocal_ranks) / max(1, len(reciprocal_ranks)), 4)
    avg_precision = round(sum(precisions_at_k) / max(1, len(precisions_at_k)), 4)
    avg_recall = round(sum(recalls_at_k) / max(1, len(recalls_at_k)), 4)
    hit_rate = round(sum(hits_at_k) / max(1, len(hits_at_k)), 4)

    metrics = {
        "queries_evaluated": len(queries),
        "k": k,
        "mrr": mrr,
        "precision_at_k": avg_precision,
        "recall_at_k": avg_recall,
        "hit_rate_at_k": hit_rate,
        "evaluation_status": "PASS" if mrr >= 0.80 and hit_rate >= 0.80 else "FAIL",
    }

    report_path = Path(__file__).parent / "retrieval_metrics.json"
    report_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return metrics


def test_retrieval_benchmark_meets_accuracy_thresholds():
    metrics = run_retrieval_evaluation()
    assert metrics["mrr"] >= 0.80, f"MRR {metrics['mrr']} below threshold 0.80"
    assert metrics["hit_rate_at_k"] >= 0.80, f"Hit rate {metrics['hit_rate_at_k']} below threshold 0.80"
    assert metrics["evaluation_status"] == "PASS"


if __name__ == "__main__":
    result = run_retrieval_evaluation()
    print("Retrieval Evaluation Results:")
    print(json.dumps(result, indent=2))
