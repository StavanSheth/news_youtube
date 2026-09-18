"""Canonical production pipeline orchestrator."""

from __future__ import annotations

import json
import logging
import os
from datetime import timedelta
from html import escape
from pathlib import Path
from typing import Any

from ..budgets import BudgetManager
from ..classification import relevance, topic_matches
from ..contracts import (
    RunContext,
    TimestampStatus,
    source_timestamps_from_mapping,
)
from ..emailer import send_digest
from ..enrichment import confidence_score, detect_opportunities, extract_entities, trend_signals
from ..events import group_events, importance as event_importance
from ..identity import make_content_id, make_source_id
from ..infrastructure.clock import now_utc
from ..infrastructure.config import load_application_config
from ..ingestion import enriched_rss
from ..manager import IntelligenceManager
from ..microtopics import catalog, classify_micro_topics, coverage
from ..newsletter import NewsletterModel
from ..persistence import PersistencePaths
from ..provider import DryRunProvider, GeminiProvider
from ..publication import archive_edition_run
from ..quality import evaluate_output
from ..source_validation import validate_source_registry
from ..sources import discover_youtube
from ..state import RepositoryState
from ..statuses import DeliveryStatus, SourceStatus
from .edition_runner import resolve_edition_context

LOGGER = logging.getLogger(__name__)


def eligible_for_edition(
    item: dict[str, Any],
    lookback_floor: Any,
    publication_cutoff: Any,
) -> bool:
    """Check if item timestamp falls within valid lookback and publication cutoff window."""
    timestamps = source_timestamps_from_mapping(item)
    return bool(
        timestamps.publication_status == TimestampStatus.VALID
        and timestamps.published_at
        and lookback_floor <= timestamps.published_at <= publication_cutoff
    )


def render_newsletter(
    root: Path,
    stories: list[dict[str, Any]],
    micro_topic_coverage: list[dict[str, Any]] | None = None,
    source_health: dict[str, Any] | None = None,
    run_context: RunContext | None = None,
) -> tuple[Path, Path]:
    """Render markdown and HTML newsletter from validated intelligence stories."""
    run_time = now_utc()
    output = (
        PersistencePaths.for_root(root).run_dir(run_context)
        if run_context
        else root / "output" / run_time.strftime("%Y/%m/%d/%H%M")
    )
    output.mkdir(parents=True, exist_ok=True)

    edition_key = run_context.edition_key if run_context else run_time.isoformat()
    newsletter = NewsletterModel.from_stories(
        stories, edition_key, micro_topic_coverage, source_health
    )

    executive = newsletter.executive_summary
    markdown = [
        "# Daily Intelligence",
        f"**Edition:** {newsletter.edition}",
        "",
        "## Executive Brief",
    ]
    markdown += [
        f"- **{story['title']}** ({story['change']}, {story['importance_score']:.0f}/100)"
        for story in executive
    ] or ["- No new high-value developments."]

    markdown += ["", "## Top Events"]
    markdown += [
        f"- **{story['title']}**: {story.get('change', 'NEW')} | confidence {story.get('confidence_score', 0):.0f}/100"
        for story in newsletter.top_events
    ] or ["- No events met the high-importance threshold."]

    sections = (
        ("News Intelligence", newsletter.news_intelligence),
        ("Case Studies", newsletter.case_studies),
        ("Tutorials & Engineering", newsletter.tutorials_engineering),
        ("Podcasts & Interviews", newsletter.podcasts_interviews),
        ("Specialist Research", newsletter.specialist_research),
    )
    for title, stream_stories in sections:
        if not stream_stories:
            continue
        markdown += ["", f"## {title}"]
        for story in stream_stories:
            markdown += [
                f"### {story['title']}",
                f"**Theme:** {story.get('theme', 'domain-fallback')} | **Importance:** {story.get('importance_score', 0):.0f}/100 | **Confidence:** {story.get('confidence_score', 0):.0f}/100",
                "",
                "**Key Facts:**",
            ]
            markdown += [f"- {fact}" for fact in story.get("analysis", {}).get("facts", [])] or [
                "- No primary facts recorded."
            ]
            markdown += ["", "**Interpretation:**"]
            markdown += [
                f"- {item}" for item in story.get("analysis", {}).get("interpretation", [])
            ] or ["- Standard analytical baseline applies."]
            actions = story.get("analysis", {}).get("actionable_insights", [])
            if actions:
                markdown += ["", "**Actionable Implications:**"]
                markdown += [f"- {action}" for action in actions]
            markdown.append("")

    markdown += ["", "## Micro-topic Coverage"]
    for entry in micro_topic_coverage or []:
        status = entry.get("status", "NOT_EVALUATED")
        status_label = entry.get("label", status)
        markdown.append(
            f"- **{entry.get('domain', '')} / {entry.get('micro_topic', '')}**: {status_label}"
        )

    cards = []
    for title, stream_stories in sections:
        if not stream_stories:
            continue
        cards.append(f"<section><h2>{escape(title)}</h2>")
        for story in stream_stories:
            facts = "".join(
                f"<li>{escape(fact)}</li>"
                for fact in story.get("analysis", {}).get("facts", [])[:3]
            )
            cards.append(
                f"<article style='margin-bottom:16px;padding:12px;border:1px solid #e0e0e0;border-radius:4px'>"
                f"<h3><a href='{escape(story.get('url', '#'))}'>{escape(story['title'])}</a></h3>"
                f"<p><strong>Theme:</strong> {escape(str(story.get('theme', '')))} | <strong>Importance:</strong> {story.get('importance_score', 0):.0f}/100</p>"
                f"<ul>{facts}</ul></article>"
            )
        cards.append("</section>")

    coverage_html = "".join(
        f"<li>{escape(str(entry.get('micro_topic', '')))}: {escape(str(entry.get('label', entry.get('status', ''))))}</li>"
        for entry in (micro_topic_coverage or [])[:15]
    )
    health_html = "".join(
        f"<li>{escape(value.get('source', ''))}: {escape(str(value.get('status', '')))} ({value.get('entries', 0)} entries)</li>"
        for value in (source_health or {}).values()
    )

    brief_items = "".join(f"<li>{escape(s['title'])}</li>" for s in executive)
    brief_html = brief_items or "<li>No new high-value developments.</li>"
    cards_html = "".join(cards)

    html = (
        "<!doctype html><html><body style='margin:0;background:#eef2f5;font-family:Arial,sans-serif;color:#17212b'>"
        "<table role='presentation' width='100%'><tr><td align='center' style='padding:24px'>"
        "<table role='presentation' width='640' style='max-width:640px;background:#fff;border-collapse:collapse'>"
        f"<tr><td style='padding:28px;background:#102f43;color:#fff'><h1 style='margin:0'>Daily Intelligence</h1><p style='margin:8px 0 0'>{run_time:%d %b %Y} | {run_time:%H:%M UTC}</p></td></tr>"
        f"<tr><td style='padding:22px'><h2>Executive Brief</h2><ul>{brief_html}</ul></td></tr>"
        f"{cards_html}"
        f"<tr><td style='padding:22px'><h2>Micro-topic Coverage</h2><ul>{coverage_html or '<li>Insufficient evidence collected.</li>'}</ul><h2>Source Health</h2><ul>{health_html or '<li>No enabled sources were checked.</li>'}</ul></td></tr>"
        "<tr><td style='padding:18px;background:#edf1f4;color:#5d6973;font-size:12px'>Source facts and AI interpretation are intentionally separated.</td></tr>"
        "</table></td></tr></table></body></html>"
    )


    markdown_path = output / "digest.md"
    html_path = output / "digest.html"
    markdown_path.write_text("\n".join(markdown) + "\n", encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    return markdown_path, html_path


class CanonicalPipeline:
    """Authoritative production pipeline orchestrator adhering strictly to Set E."""

    def __init__(self, root: Path, dry_run: bool = False, fixture_path: Path | None = None) -> None:
        self.root = root.resolve()
        self.dry_run = dry_run
        self.fixture_path = fixture_path
        self.config = load_application_config(self.root)
        self.started = now_utc()
        self.paths = PersistencePaths.for_root(self.root)
        self.paths.ensure()
        self.edition_context, self.run_context = resolve_edition_context(
            self.config.settings, self.started, self.config.versions
        )
        self.state = RepositoryState(self.paths, self.config.settings.get("state", {}))
        self.pipe_config = self.config.settings.get("pipeline", {})

    def run(self) -> tuple[Path, Path]:
        """Execute the end-to-end canonical intelligence pipeline."""
        # 1. Collection & Ingestion
        source_health: dict[str, dict[str, Any]] = {}
        feeds = self.config.settings.get("news", {}).get(
            "sources", self.config.settings.get("news", {}).get("feeds", [])
        )
        source_validation = (
            validate_source_registry(feeds)
            if not self.fixture_path
            else {
                "fixture": {
                    "source": "Fixture corpus",
                    "source_id": "fixture",
                    "enabled": True,
                    "status": "HEALTHY",
                    "item_count": 0,
                    "usable_content_count": 0,
                    "relevant_content_count": 0,
                    "trust_tier": 1,
                }
            }
        )

        if self.fixture_path:
            fixture_items = json.loads(self.fixture_path.read_text(encoding="utf-8"))
            discovered = []
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
                        "retrieved_at": self.started.isoformat(),
                        **item.get("metadata", {}),
                    },
                })
            source_health["fixture"] = {
                "status": SourceStatus.HEALTHY.value,
                "entries": len(discovered),
                "source": "Fixture corpus",
                "trust_tier": 1,
            }
            source_validation["fixture"].update({
                "item_count": len(discovered),
                "usable_content_count": sum(
                    bool(item.get("title") and item.get("url")) for item in discovered
                ),
                "relevant_content_count": len(discovered),
            })
        else:
            discovered = [
                item.to_dict()
                for item in enriched_rss(
                    feeds,
                    fetch_articles=bool(
                        self.config.settings.get("news", {}).get("fetch_articles", True)
                    ),
                    source_health=source_health,
                )
            ]
            if os.getenv("YOUTUBE_API_KEY"):
                try:
                    discovered += [
                        item.to_dict()
                        for item in discover_youtube(
                            self.config.channels,
                            self.config.topics,
                            os.environ["YOUTUBE_API_KEY"],
                            int(self.pipe_config.get("max_keyword_results_per_topic", 0)),
                            bool(self.pipe_config.get("allow_global_youtube_discovery", False)),
                        )
                    ]
                except Exception as error:
                    LOGGER.warning("YouTube discovery failed: %s", type(error).__name__)

        # 2. Event Grouping
        event_groups = group_events(discovered)
        discovered = [
            {
                **group["items"][0],
                "metadata": {
                    **group["items"][0].get("metadata", {}),
                    "event_id": group["event_id"],
                    "corroboration": group["corroboration"],
                    "related_sources": group["related_sources"],
                },
            }
            for group in event_groups
        ]

        # 3. Deterministic Identity & Timestamps
        timestamp_status_counts: dict[str, int] = {}
        for item in discovered:
            metadata = item.setdefault("metadata", {})
            source_key = (
                metadata.get("source_key")
                or metadata.get("source_id")
                or item.get("source", "unknown")
            )
            metadata["source_key"] = source_key
            metadata["source_id"] = make_source_id(source_key)
            metadata.setdefault(
                "content_id",
                make_content_id(
                    metadata["source_id"],
                    item.get("url", ""),
                    item.get("title", ""),
                    item.get("published_at", ""),
                    item.get("text", ""),
                ),
            )
            metadata.setdefault("retrieved_at", self.started.isoformat())
            timestamps = source_timestamps_from_mapping(item, self.started)
            metadata["timestamp_status"] = timestamps.publication_status.value
            metadata["published_at_status"] = timestamps.published_at_status.value
            metadata["updated_at_status"] = timestamps.updated_at_status.value
            metadata["retrieved_at_status"] = timestamps.retrieved_at_status.value
            status_val = timestamps.publication_status.value
            timestamp_status_counts[status_val] = timestamp_status_counts.get(status_val, 0) + 1
            if timestamps.published_at:
                item["published_at"] = timestamps.published_at.isoformat()
            if timestamps.updated_at:
                metadata["updated_at"] = timestamps.updated_at.isoformat()
            if timestamps.retrieved_at:
                metadata["retrieved_at"] = timestamps.retrieved_at.isoformat()

        # 4. Cheap Filtering & Eligibility
        lookback_floor = self.edition_context.publication_cutoff_utc - timedelta(
            days=int(self.pipe_config.get("lookback_days", 7))
        )
        publication_cutoff = self.edition_context.publication_cutoff_utc
        eligible = [
            item
            for item in discovered
            if eligible_for_edition(item, lookback_floor, publication_cutoff)
            and (bool(self.fixture_path) or not self.state.seen(item))
            and self.state.retry_due(item["id"])
        ]

        # 5. AI Provider & Manager Setup
        provider = (
            DryRunProvider()
            if self.dry_run
            else GeminiProvider(
                os.environ["GEMINI_API_KEY"],
                self.config.settings["gemini"],
                self.config.prompts,
            )
        )
        manager_settings = {
            **self.config.settings.get("gemini", {}),
            **self.config.settings.get("retrieval", {}),
            **self.config.settings.get("pipeline", {}),
        }
        budget_manager = BudgetManager(self.config.settings.get("budgets", {}))
        manager = IntelligenceManager(
            provider,
            self.config.themes,
            manager_settings,
            budget=budget_manager,
            run_context=self.run_context,
            edition_context=self.edition_context,
        )

        micro_topic_catalog = catalog(
            self.config.taxonomy,
            self.config.topics,
            self.config.microtopics,
            self.config.microtopic_matrix,
            self.config.profile_templates,
        )

        # 6. Micro-Topic Execution Loop
        stories: list[dict[str, Any]] = []
        compact: list[dict[str, Any]] = []
        coverage_assignments: list[dict[str, Any]] = []

        max_items = int(self.pipe_config.get("max_items_per_run", 20))
        sorted_eligible = sorted(
            eligible, key=lambda entry: entry.get("published_at", ""), reverse=True
        )[:max_items]

        for item in sorted_eligible:
            topics = topic_matches(item, self.config.topics)
            micro_topics = classify_micro_topics(item, micro_topic_catalog)
            for micro_topic in micro_topics:
                if not any(t["key"] == micro_topic["topic_key"] for t in topics):
                    topics.append({
                        "key": micro_topic["topic_key"],
                        "name": micro_topic["topic"],
                        "score": micro_topic["confidence"],
                        "config": {"priority": micro_topic["priority"]},
                        "matches": micro_topic["signals"],
                    })

            importance = relevance(item, topics, self.config.settings.get("scoring", {}))
            min_rel = float(self.pipe_config.get("min_relevance_score", 0.35))
            if not topics or not micro_topics or importance < min_rel:
                self.state.success(item, topics, importance, "LOW_VALUE")
                continue

            try:
                results = manager.analyze(item, micro_topics)
                for micro_topic in micro_topics:
                    matched_result = next(
                        (
                            r
                            for r in results
                            if r["classification"]["micro_topic"] == micro_topic["micro_topic"]
                        ),
                        None,
                    )
                    corrob = (
                        item.get("metadata", {}).get("corroboration", {}).get("source_count", 1)
                    )
                    weights = self.config.settings.get("scoring", {}).get("importance_weights")
                    eval_status = (
                        "FAILED"
                        if not matched_result
                        or (
                            matched_result.get("retrieval", {}).get("status")
                            == "RETRIEVAL_FAILURE"
                        )
                        or matched_result.get("analysis_status") == "ANALYSIS_FAILURE"
                        else "EVALUATION_COMPLETE"
                    )
                    coverage_assignments.append({
                        **micro_topic,
                        "importance_score": event_importance(importance, corrob, weights=weights),
                        "evidence_available": bool(matched_result and matched_result.get("evidence")),
                        "candidate_count": int(bool(matched_result)),
                        "relevant_count": int(
                            bool(matched_result and matched_result.get("evidence"))
                        ),
                        "event_count": int(bool(item.get("metadata", {}).get("event_id"))),
                        "publishable_count": int(
                            bool(
                                matched_result
                                and matched_result.get("evidence")
                                and matched_result.get("analysis_status") == "OK"
                            )
                        ),
                        "retrieval_status": (matched_result or {}).get("retrieval", {}).get("status", "EMPTY_RETRIEVAL"),
                        "analysis_status": (matched_result or {}).get("analysis_status", "ANALYSIS_FAILURE"),
                        "evaluation_status": eval_status,
                    })

                if not results:
                    self.state.success(item, topics, importance, "LOW_EVIDENCE")
                    continue

                entities = extract_entities(
                    f"{item.get('title', '')}\n{item.get('text', '')}", self.config.entities
                )
                corroboration = (
                    item.get("metadata", {}).get("corroboration", {}).get("source_count", 1)
                )
                change = self.state.change_status(item)

                for result in results:
                    analysis = result.get("analysis", {})
                    if (
                        not analysis
                        or not result.get("evidence")
                        or result.get("analysis_status") != "OK"
                    ):
                        continue
                    weights = self.config.settings.get("scoring", {}).get("importance_weights")
                    story = {
                        **item,
                        "topics": topics,
                        "micro_topics": [result["classification"]],
                        "theme": result["theme"].get("id", "domain-fallback"),
                        "report_type": result["theme"]
                        .get("output", {})
                        .get("report_type", "short_summary"),
                        "retrieved_evidence": result["evidence"],
                        "importance": importance,
                        "importance_score": event_importance(
                            importance, corroboration, weights=weights
                        ),
                        "confidence_score": round(
                            confidence_score(item, analysis, corroboration) * 100
                        ),
                        "entities": entities,
                        "opportunities": detect_opportunities(item, analysis),
                        "content_id": item.get("metadata", {}).get("content_id", ""),
                        "source_id": item.get("metadata", {}).get("source_id", ""),
                        "region": item.get("metadata", {}).get("region", "global"),
                        "country": item.get("metadata", {}).get("country", "GLOBAL"),
                        "content_type": item.get("metadata", {}).get("content_type", "news"),
                        "change": change,
                        "analysis": analysis,
                    }
                    stories.append(story)

                compact.append({
                    "id": item["id"],
                    "title": item["title"],
                    "processed_at": now_utc().isoformat(),
                    "topics": [t["key"] for t in topics],
                    "content_hash": item.get("id", ""),
                    "content_id": item.get("metadata", {}).get("content_id", ""),
                    "source_id": item.get("metadata", {}).get("source_id", ""),
                })
                self.state.success(item, topics, importance, change)

            except Exception as error:
                self.state.failure(item, error)
                LOGGER.warning("failed item %s: %s", item["id"], type(error).__name__)

        # 7. Coverage Ledger & Summary
        evaluation_ledger: dict[str, Any] = {}
        for entry in micro_topic_catalog:
            assignments = [
                a
                for a in coverage_assignments
                if a["domain"] == entry["domain"] and a["micro_topic"] == entry["micro_topic"]
            ]
            key = f"{entry['domain']}:{entry['micro_topic']}"
            evaluation_ledger[key] = {
                "evaluation_status": (
                    "FAILED"
                    if any(a.get("evaluation_status") == "FAILED" for a in assignments)
                    else "EVALUATION_COMPLETE"
                    if assignments
                    and all(a.get("evaluation_status") == "EVALUATION_COMPLETE" for a in assignments)
                    else "NOT_STARTED"
                ),
                "sources_checked": len(source_health),
                "candidate_count": sum(int(a.get("candidate_count", 0)) for a in assignments),
                "relevant_count": sum(int(a.get("relevant_count", 0)) for a in assignments),
                "evidence_count": sum(int(a.get("evidence_count", 0)) for a in assignments),
            }

        source_summary = {
            "healthy_sources": sum(
                1 for v in source_health.values() if v.get("status") == "HEALTHY"
            ),
            "checked_sources": len(source_health),
            "evaluated_micro_topics": sorted({
                f"{a['domain']}:{a['micro_topic']}" for a in coverage_assignments
            }),
            "evaluation_ledger": evaluation_ledger,
            "source_failures": [
                {
                    "source": v.get("source"),
                    "source_id": sid,
                    "status": v.get("status"),
                    "error": v.get("error"),
                    "failure_reason": v.get("failure_reason"),
                }
                for sid, v in source_health.items()
                if v.get("status")
                in {SourceStatus.FAILED.value, SourceStatus.SOURCE_UNAVAILABLE.value}
            ],
        }

        micro_topic_coverage = coverage(
            micro_topic_catalog, coverage_assignments, source_summary
        )

        # 8. Newsletter Rendering
        markdown, html = render_newsletter(
            self.root, stories, micro_topic_coverage, source_health, self.run_context
        )

        # 9. Quality Evaluation & Hard Gates
        quality = evaluate_output(
            stories,
            markdown.read_text(encoding="utf-8"),
            html.read_text(encoding="utf-8"),
            micro_topic_coverage,
            source_health,
        )

        (markdown.parent / "quality.json").write_text(
            json.dumps(quality, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (markdown.parent / "source_validation.json").write_text(
            json.dumps(source_validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (markdown.parent / "coverage.json").write_text(
            json.dumps(micro_topic_coverage, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        # 10. Archive Run
        archive_edition_run(
            self.paths.archive,
            self.edition_context.edition_key,
            self.run_context.run_id,
            {
                "digest.md": markdown.read_text(encoding="utf-8"),
                "digest.html": html.read_text(encoding="utf-8"),
                "quality.json": quality,
                "source_validation.json": source_validation,
                "coverage.json": micro_topic_coverage,
            },
        )

        # Append quality gate to output files
        markdown.write_text(
            markdown.read_text(encoding="utf-8")
            + "\n## Quality Gate\n"
            + f"- Overall deterministic quality score: {quality['scores']['overall']}/100\n"
            + f"- Gate status: {'PASS' if quality['passed'] else 'REVIEW REQUIRED'}\n",
            encoding="utf-8",
        )
        html.write_text(
            html.read_text(encoding="utf-8").replace(
                "</body>",
                f"<section><h2>Quality Gate</h2><p>Overall deterministic quality score: {quality['scores']['overall']}/100. Status: {'PASS' if quality['passed'] else 'REVIEW REQUIRED'}.</p></section></body>",
            ),
            encoding="utf-8",
        )

        # 11. State & Entity / Event Tracking
        for group in event_groups:
            first = group["items"][0]
            event_id = group["event_id"]
            prev = self.state.events.get(event_id, {})
            event_stories = [
                s for s in stories if s.get("metadata", {}).get("event_id") == event_id
            ]
            self.state.events[event_id] = {
                "event_id": event_id,
                "first_seen": prev.get("first_seen", self.started.isoformat()),
                "last_seen": now_utc().isoformat(),
                "status": "UPDATED" if prev else "NEW",
                "title": first.get("title", ""),
                "entities": group.get("entities", []),
                "domains": sorted({
                    t.get("domain", "")
                    for s in event_stories
                    for t in s.get("micro_topics", [])
                }),
                "topics": sorted({
                    t.get("key", t.get("name", ""))
                    for s in event_stories
                    for t in s.get("topics", [])
                }),
                "micro_topics": sorted({
                    t.get("micro_topic", "")
                    for s in event_stories
                    for t in s.get("micro_topics", [])
                }),
                "sources": group.get("related_sources", []),
                "corroboration": group.get("corroboration", {}),
                "importance": max(
                    (s.get("importance_score", 0) for s in event_stories), default=0
                ),
                "confidence": max(
                    (s.get("confidence_score", 0) for s in event_stories), default=0
                ),
                "evidence": [
                    entry
                    for s in event_stories
                    for entry in s.get("analysis", {}).get("evidence", [])
                ],
                "related_events": prev.get("related_events", []),
            }

        for story in stories:
            for entity in story.get("entities", []):
                ent_key = entity["name"].lower()
                self.state.entities.setdefault(
                    ent_key,
                    {
                        "name": entity["name"],
                        "type": entity["type"],
                        "events": [],
                        "first_seen": self.started.isoformat(),
                    },
                )
                self.state.entities[ent_key]["last_seen"] = now_utc().isoformat()
                event_id = story.get("metadata", {}).get("event_id", story["id"])
                if event_id not in self.state.entities[ent_key]["events"]:
                    self.state.entities[ent_key]["events"].append(event_id)

        for trend in trend_signals(stories):
            self.state.trends[trend["type"] + ":" + trend["key"]] = {
                **trend,
                "updated_at": now_utc().isoformat(),
            }

        self.state.finish(
            {
                "started": self.started.isoformat(),
                "completed": now_utc().isoformat(),
                "run_id": self.run_context.run_id,
                "edition": self.edition_context.edition.value,
                "edition_key": self.edition_context.edition_key,
                "edition_timezone": self.edition_context.timezone,
                "publication_cutoff_local": self.edition_context.publication_cutoff_local.isoformat(),
                "publication_cutoff_utc": self.edition_context.publication_cutoff_utc.isoformat(),
                "versions": self.config.versions.to_dict(),
                "timestamp_status_counts": timestamp_status_counts,
                "discovered": len(discovered),
                "eligible": len(eligible),
                "processed": len(compact),
                "micro_topic_analyses": len(stories),
                "failed": sum(1 for item in eligible if item["id"] in self.state.failures),
                "source_health": source_health,
                "micro_topic_coverage": micro_topic_coverage,
                "quality": quality,
                "run_status": quality["status"],
                "manager_stats": manager.stats,
                "report": str(markdown.relative_to(self.root)),
            },
            compact,
        )

        # 12. Delivery with Idempotency
        delivery = {
            "status": (
                DeliveryStatus.SKIPPED_DRY_RUN if self.dry_run else DeliveryStatus.DISABLED
            ).value,
            "updated_at": now_utc().isoformat(),
        }
        self.paths.data_file("source_validation.json").write_text(
            json.dumps(source_validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        if (
            self.config.settings.get("email", {}).get("enabled")
            and not self.dry_run
            and quality["passed"]
        ):
            try:
                send_digest(
                    html,
                    markdown,
                    f"{self.config.settings['email'].get('subject_prefix', 'Daily Intelligence')} - {self.started:%d %b %Y %H:%M}",
                )
                delivery = {
                    "status": DeliveryStatus.DELIVERY_CONFIRMED.value,
                    "updated_at": now_utc().isoformat(),
                }
            except Exception as error:
                LOGGER.warning("SMTP delivery failed: %s", type(error).__name__)
                delivery = {
                    "status": DeliveryStatus.DELIVERY_FAILED.value,
                    "error_type": type(error).__name__,
                    "updated_at": now_utc().isoformat(),
                }
        elif not self.dry_run and not quality["passed"]:
            delivery = {
                "status": DeliveryStatus.QUALITY_REVIEW_REQUIRED.value,
                "updated_at": now_utc().isoformat(),
            }

        self.paths.data_file("delivery_state.json").write_text(
            json.dumps(delivery, indent=2) + "\n", encoding="utf-8"
        )

        return markdown, html


def run_pipeline(
    root: Path,
    dry_run: bool = False,
    fixture_path: Path | None = None,
) -> tuple[Path, Path]:
    """Authoritative entrypoint to run the canonical intelligence pipeline."""
    pipeline = CanonicalPipeline(root, dry_run=dry_run, fixture_path=fixture_path)
    return pipeline.run()
