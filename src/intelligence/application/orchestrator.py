"""Authoritative ApplicationOrchestrator coordinating the 16-step canonical edition pipeline."""

from __future__ import annotations

import json
import logging
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

from ..ai import DryRunProvider, GeminiProvider
from ..budgets.manager import BudgetManager
from ..contracts import (
    source_timestamps_from_mapping,
)
from ..emailer import send_digest
from ..enrichment import detect_opportunities, extract_entities
from ..identity import make_content_id
from ..infrastructure.clock import now_utc
from ..infrastructure.config import load_application_config
from ..ingestion import enriched_rss
from ..microtopics import catalog
from ..newsletter import NewsletterModel, render_html, render_markdown
from ..observability import default_metrics
from ..persistence import PersistencePaths, ProductionRepository
from ..rag.manager import ProductionRAGManager
from ..sources import discover_youtube
from ..state import RepositoryState
from ..statuses import SourceStatus
from ..validation.pipeline import validate_analysis
from .edition_runner import EditionRunner
from .item_processor import ItemProcessor
from .lifecycle import RunLifecycleStage

LOGGER = logging.getLogger(__name__)


class ApplicationOrchestrator:
    """Authoritative orchestrator coordinating the complete edition run through all 16 lifecycle stages."""

    def __init__(
        self,
        root: Path,
        dry_run: bool = False,
        fixture_path: Path | None = None,
        settings: dict[str, Any] | None = None,
    ) -> None:
        self.root = root.resolve()
        self.dry_run = dry_run
        self.fixture_path = fixture_path
        
        config_dir = self.root / "config"
        repo_root = self.root if config_dir.is_dir() else Path(__file__).parents[3]
        self.config = load_application_config(repo_root)
        if settings:
            self.config.settings.update(settings)

        self.paths = PersistencePaths.for_root(self.root)
        self.paths.ensure()
        self.repository = ProductionRepository(self.paths)
        self.runner = EditionRunner(
            self.config.settings, self.paths, self.repository, self.config.versions
        )
        self.state = RepositoryState(self.paths, self.config.settings.get("state", {}))
        self.budget_manager = BudgetManager(
            self.config.settings.get("budgets", {}).get("limits", self.config.settings.get("budgets", {})),
            self.config.settings.get("budgets", {}).get("micro_topics", {}),
        )
        micro_catalog = catalog(
            self.config.taxonomy,
            self.config.topics,
            self.config.microtopics,
            self.config.microtopic_matrix,
            self.config.profile_templates,
        )
        self.processor = ItemProcessor(
            themes=self.config.themes,
            micro_topic_catalog=micro_catalog,
            settings=self.config.settings,
        )
        self.metrics = default_metrics

    def run_edition(self) -> tuple[Path, Path]:
        """Execute all 16 canonical stages from initialization to delivery and closure."""
        # Stage 1: INITIALIZING
        started = now_utc()
        edition_context, run_context = self.runner.start(started)
        LOGGER.info("Initialized edition %s (run_id=%s)", edition_context.edition_key, run_context.run_id)

        # Stage 2: COLLECTING
        discovered: list[dict[str, Any]] = []
        source_health: dict[str, dict[str, Any]] = {}
        feeds = self.config.settings.get("news", {}).get(
            "sources", self.config.settings.get("news", {}).get("feeds", [])
        )

        if self.fixture_path:
            fixture_items = json.loads(self.fixture_path.read_text(encoding="utf-8"))
            for index, item in enumerate(fixture_items):
                discovered.append({
                    "id": item.get("id", f"fixture-{index}"),
                    "kind": item.get("kind", "news"),
                    "title": item.get("title", "Fixture item"),
                    "url": item.get("url", "https://fixture.test/item"),
                    "text": item.get("text", ""),
                    "published_at": item.get("published_at", ""),
                    "source": item.get("source", "Fixture"),
                    "priority": item.get("priority", 8),
                    "metadata": {
                        "source_id": "fixture",
                        "source_type": "fixture",
                        "trust_tier": 1,
                        "retrieved_at": started.isoformat(),
                        **item.get("metadata", {}),
                    },
                })
            source_health["fixture"] = {
                "status": SourceStatus.HEALTHY.value,
                "entries": len(discovered),
            }
        else:
            fetch_articles = bool(self.config.settings.get("news", {}).get("fetch_articles", True)) and not self.dry_run
            try:
                rss_items = enriched_rss(feeds, fetch_articles=fetch_articles, source_health=source_health)
                discovered.extend([item.to_dict() for item in rss_items])
            except Exception as exc:
                LOGGER.warning("RSS collection failed: %s", exc)

            # Discover YouTube sources
            yt_channels = self.config.settings.get("youtube", {}).get("channels", [])
            yt_key = os.environ.get("YOUTUBE_API_KEY", "")
            if yt_channels and yt_key and not self.dry_run:
                try:
                    discovered.extend(discover_youtube(yt_channels, yt_key))
                except Exception as exc:
                    LOGGER.warning("YouTube discovery failed: %s", exc)

        # Stage 3: NORMALIZING & Stage 4: FILTERING
        lookback_days = int(self.config.settings.get("pipeline", {}).get("lookback_days", 3))
        lookback_floor = started - timedelta(days=lookback_days)
        cutoff = edition_context.publication_cutoff_utc

        filtered_items: list[dict[str, Any]] = []
        for raw_item in discovered:
            ts = source_timestamps_from_mapping(raw_item)
            text = raw_item.get("text", "").strip()
            # Cheap filter: text must be present
            if not text and not raw_item.get("title"):
                continue
            # Lookback and publication cutoff check
            if ts.published_at and (ts.published_at < lookback_floor or ts.published_at > cutoff):
                continue
            filtered_items.append(raw_item)

        # Stage 5: DEDUPLICATING
        seen_urls: set[str] = set()
        seen_contents: set[str] = set()
        deduped_items: list[dict[str, Any]] = []

        for item in filtered_items:
            url = item.get("url", "")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)

            content_id = item.get("metadata", {}).get("content_id") or make_content_id(
                item.get("source", "unknown"), url, item.get("title", ""), item.get("published_at", ""), item.get("text", "")
            )
            if content_id in seen_contents:
                continue
            seen_contents.add(content_id)

            # Persist normalized content atomically via repository
            self.repository.save_content(content_id, item)
            deduped_items.append(item)

        # Stage 6: CLASSIFYING, Stage 7: THEME ROUTING & Stage 8: CREATE MICRO-TOPIC JOBS
        processed_items = [self.processor.process_item(item) for item in deduped_items]

        # Stage 9: RETRIEVE EVIDENCE & Stage 10: RUN AI
        rag_manager = ProductionRAGManager(self.config.settings)
        for proc in processed_items:
            rag_manager.index_item(proc.normalized_item)

        ai_provider = (
            DryRunProvider()
            if self.dry_run or self.fixture_path
            else GeminiProvider(
                key=os.environ.get("GEMINI_API_KEY", ""),
                config=self.config.settings.get("models", {}).get("gemini", {"model": "gemini-2.5-flash"}),
                prompts=self.config.settings.get("prompts", {}),
            )
        )

        analyzed_stories: list[dict[str, Any]] = []

        for proc in processed_items:
            norm_item = proc.normalized_item
            for job in proc.micro_topic_jobs:
                cls_info = job["classification"]
                theme = job["theme"]

                # RAG retrieval
                rag_res = rag_manager.retrieve(
                    norm_item,
                    cls_info,
                    theme,
                    edition_context=edition_context,
                    run_context=run_context,
                )
                if rag_res.get("status") != "OK":
                    continue

                context_packet = rag_res["context_packet"]

                micro_id = str(cls_info.get("micro_topic_id") or cls_info.get("micro_topic", ""))
                can_run, reason, skip_rec = self.budget_manager.authorize(
                    micro_id,
                    priority="P0" if int(job.get("priority", 5)) >= 8 else "P1",
                    estimated_calls=1,
                    estimated_chars=len(str(context_packet)),
                    run_id=run_context.run_id,
                )
                if not can_run:
                    LOGGER.warning("Budget skipped AI for micro-topic %s: %s", micro_id, reason)
                    if skip_rec:
                        self.repository.save_budget_snapshot(
                            f"skip_{run_context.run_id}_{micro_id}",
                            skip_rec.to_dict(),
                        )
                    continue

                # AI Analysis
                analysis_output = ai_provider.analyze_micro_topic(
                    norm_item,
                    cls_info,
                    list(context_packet["retrieved_evidence"]),
                )
                self.budget_manager.consume(micro_id, "ai_calls", 1)
                self.budget_manager.consume(micro_id, "context_chars", len(str(context_packet)))

                # Stage 11: VALIDATING (5-stage)
                val_res = validate_analysis(
                    analysis_output,
                    micro_topic_job=job,
                    context_packet=context_packet,
                )
                if not val_res.is_publishable:
                    LOGGER.warning("Validation rejected story %s: %s", norm_item.get("title"), val_res.errors)
                    continue

                story_entry = {
                    **norm_item,
                    "analysis": analysis_output,
                    "topics": [cls_info.get("micro_topic_id") or cls_info.get("micro_topic", "")],
                    "importance_score": 75,
                    "validation": val_res.to_dict(),
                }
                analyzed_stories.append(story_entry)
                self.repository.save_analysis(
                    f"{proc.content_id}_{job['micro_topic_id']}",
                    story_entry,
                )

        # Stage 12: ENRICHING
        # Event grouping & entity extraction
        for story in analyzed_stories:
            story["entities"] = extract_entities(story.get("text", ""))
            story["opportunities"] = detect_opportunities(story, story.get("analysis", {}))

        # Stage 13: ASSEMBLING
        newsletter = NewsletterModel.from_stories(
            stories=analyzed_stories,
            edition=edition_context.edition_key,
            micro_topic_coverage=[],
            source_health=source_health,
        )

        # Stage 14: RENDERING
        output_dir = self.paths.run_dir(run_context)
        output_dir.mkdir(parents=True, exist_ok=True)
        md_file = output_dir / "digest.md"
        html_file = output_dir / "digest.html"

        md_content = render_markdown(newsletter)
        html_content = render_html(newsletter)

        md_file.write_text(md_content, encoding="utf-8")
        html_file.write_text(html_content, encoding="utf-8")

        # Stage 15: PERSISTENCE & Stage 16: DELIVER & CLOSE RUN
        counts = {
            "discovered": len(discovered),
            "filtered": len(filtered_items),
            "deduped": len(deduped_items),
            "stories_analyzed": len(analyzed_stories),
            "newsletter_stories": len(newsletter.stories),
        }
        self.runner.finalize(
            status=RunLifecycleStage.COMPLETED.value,
            counts=counts,
        )

        # Optional SMTP delivery
        if not self.dry_run and not self.fixture_path:
            email_cfg = self.config.settings.get("email", {})
            if email_cfg.get("enabled"):
                try:
                    send_digest(html_content, email_cfg)
                    self.repository.save_delivery(
                        run_context.run_id,
                        {"status": "SENT", "timestamp": now_utc().isoformat()},
                    )
                except Exception as exc:
                    LOGGER.error("SMTP delivery failed: %s", exc)

        return md_file, html_file
