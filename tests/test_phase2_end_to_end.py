"""End-to-end integration and golden dataset acceptance tests for Phase 2."""

import json
from pathlib import Path
import tempfile

from intelligence.ai import DryRunProvider
from intelligence.infrastructure.clock import SystemClock
from intelligence.newsletter import NewsletterModel, render_html, render_markdown
from intelligence.observability import MetricsRegistry
from intelligence.persistence import PersistencePaths, RunManifest
from intelligence.rag.manager import ProductionRAGManager
from intelligence.validation.pipeline import validate_analysis


def test_phase2_end_to_end_pipeline_execution():
    fixture_path = Path(__file__).parent / "fixtures" / "phase2_end_to_end" / "corpus.json"
    assert fixture_path.is_file()
    items = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert len(items) == 7

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        paths = PersistencePaths.for_root(root)
        paths.ensure()

        clock = SystemClock()
        metrics = MetricsRegistry()

        # Step 1: Ingestion and deduplication
        with metrics.timer("ingestion"):
            seen_urls = set()
            ingested_items = []
            for item in items:
                url = item.get("url", "")
                text = item.get("text", "").strip()
                # Exclude corrupt empty streams
                if not text:
                    continue
                # Exclude duplicate URLs
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                ingested_items.append(item)

        # Verified 7 items -> deduplicated to 5 items (1 duplicate dropped, 1 empty transcript dropped)
        assert len(ingested_items) == 5

        # Step 2: Micro-topic classification & RAG retrieval
        rag_manager = ProductionRAGManager({"retrieval_top_k": 3, "max_retrieved_context_chars": 6000})
        for item in ingested_items:
            rag_manager.index_item(item)

        ai_provider = DryRunProvider()
        classified_stories = []

        with metrics.timer("analysis"):
            for item in ingested_items:
                # Mock classification
                is_ai = "reasoning" in item.get("text", "").lower() or "ai" in item.get("title", "").lower()
                if not is_ai:
                    continue  # Irrelevant items (e.g. sourdough) are filtered out

                classification = {
                    "domain": "artificial-intelligence",
                    "topic": "AI",
                    "micro_topic": "foundation-models",
                    "micro_topic_id": "foundation-models",
                    "signals": ["reasoning model"],
                }
                theme = {
                    "id": "frontier-models",
                    "domain": "artificial-intelligence",
                    "questions": ["what_changed"],
                }

                item_with_class = {
                    **item,
                    "metadata": {
                        **item.get("metadata", {}),
                        "classification": classification,
                    },
                }

                # RAG retrieval
                rag_result = rag_manager.retrieve(item_with_class, classification, theme)
                assert rag_result["status"] == "OK"
                context_packet = rag_result["context_packet"]

                # AI Analysis with DryRunProvider
                analysis_dict = ai_provider.analyze_micro_topic(
                    item_with_class,
                    classification,
                    list(context_packet["retrieved_evidence"]),
                )

                # Validation Pipeline (5-stage)
                val_result = validate_analysis(
                    analysis_dict,
                    micro_topic_job={"classification": classification, "theme": theme},
                    context_packet=context_packet,
                )
                assert val_result.is_publishable is True

                classified_stories.append({
                    **item,
                    "analysis": analysis_dict,
                    "topics": ["artificial-intelligence", "foundation-models"],
                    "importance_score": 85,
                })

        # Sourdough bread item was skipped, so only reasoning model stories analyzed
        assert len(classified_stories) >= 2

        # Step 3: Assembly into NewsletterModel
        newsletter = NewsletterModel.from_stories(
            stories=classified_stories,
            edition="2026-09-18 Morning Edition",
        )
        assert len(newsletter.stories) == len(classified_stories)
        assert len(newsletter.executive_summary) >= 1

        # Step 4: Independent Renderers
        md_text = render_markdown(newsletter)
        assert "# Intelligence Digest" in md_text
        assert "Frontier AI lab releases new multimodal reasoning model" in md_text
        assert "Verified Facts" in md_text

        html_text = render_html(newsletter)
        assert "<article>" in html_text
        assert "Frontier AI lab" in html_text
        assert "Intelligence Digest" in html_text

        # Step 5: Persistence and RunManifest
        run_manifest = RunManifest(
            run_id="run-phase2-e2e-001",
            edition_key="edition-2026-09-18-morning",
            started_at=clock.now_utc().isoformat(),
            versions={"architecture": "Phase2B-2D"},
            counts={
                "ingested": len(ingested_items),
                "analyzed": len(classified_stories),
                "newsletter_stories": len(newsletter.stories),
            },
            budgets={"ai_tokens": ai_provider.cumulative_usage.total_tokens},
            metrics=metrics.snapshot(),
        )
        run_manifest.mark_completed()
        manifest_file = paths.runs / "run_manifest.json"
        run_manifest.save(manifest_file)
        assert manifest_file.is_file()

        loaded_manifest = RunManifest.load(manifest_file)
        assert loaded_manifest.status == "COMPLETED"
        assert loaded_manifest.counts["analyzed"] >= 2
        assert loaded_manifest.budgets["ai_tokens"] > 0
