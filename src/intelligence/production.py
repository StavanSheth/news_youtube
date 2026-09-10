from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import replace
from datetime import UTC, datetime, time, timedelta
from html import escape
from pathlib import Path
from typing import Any

from .config import load_config
from .emailer import send_digest
from .events import group_events
from .events import importance as event_importance
from .ingestion import enriched_rss
from .provider import DryRunProvider, GeminiProvider
from .sources import discover_youtube
from .enrichment import confidence_score, detect_opportunities, extract_entities, trend_signals
from .manager import IntelligenceManager
from .microtopics import catalog, classify_micro_topics, coverage
from .quality import evaluate_output
from .source_validation import validate_source_registry
from .contracts import EditionType, RunContext, TimestampStatus, build_edition_context, source_timestamps_from_mapping
from .identity import make_content_id, make_source_id
from .persistence import PersistencePaths
from .statuses import DeliveryStatus, SourceStatus
from zoneinfo import ZoneInfo

LOGGER = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


def parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def eligible_for_edition(item: dict[str, Any], lookback_floor: datetime, publication_cutoff: datetime) -> bool:
    timestamps = source_timestamps_from_mapping(item)
    return bool(
        timestamps.publication_status == TimestampStatus.VALID
        and timestamps.published_at
        and lookback_floor <= timestamps.published_at <= publication_cutoff
    )


def edition_context_for(settings: dict[str, Any], started_at: datetime, versions: Any) -> tuple[Any, RunContext]:
    edition_config = settings.get("edition", {})
    timezone = edition_config.get("timezone", settings.get("pipeline", {}).get("timezone", "UTC"))
    local_date = started_at.astimezone(ZoneInfo(timezone)).date()
    cutoff_value = edition_config.get("publication_cutoff_local", "23:59:59")
    cutoff = time.fromisoformat(cutoff_value) if isinstance(cutoff_value, str) else cutoff_value
    edition = build_edition_context(
        local_date,
        EditionType(str(edition_config.get("type", "NIGHT")).upper()),
        timezone,
        cutoff,
        versions,
    )
    run = RunContext.create(edition, started_at)
    return replace(edition, run_id=run.run_id), run


def content_hash(item: dict[str, Any]) -> str:
    text = "\n".join((item.get("title", ""), item.get("text", ""), item.get("url", "")))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


class RepositoryState:
    """Compact, versioned repository-file state with retry and retention controls."""

    def __init__(self, paths: PersistencePaths | Path, settings: dict[str, Any]) -> None:
        self.paths = paths if isinstance(paths, PersistencePaths) else None
        self.data_dir, self.settings = (paths.data if self.paths else paths), settings
        self.videos = self._read("processed_videos.json", {})
        self.news = self._read("processed_news.json", {})
        self.runs = self._read("processing_state.json", {"runs": [], "recent_items": []})
        self.failures = self._read("failed_items.json", {})
        self.entities = self._read("entities.json", {})
        self.events = self._read("events.json", {})
        self.trends = self._read("trends.json", {})

    def _file(self, name: str) -> Path:
        return self.paths.data_file(name) if self.paths else self.data_dir / name

    def _read(self, name: str, fallback: Any) -> Any:
        try:
            return json.loads(self._file(name).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return fallback

    def _bucket(self, kind: str) -> dict[str, Any]:
        return self.videos if kind == "youtube" else self.news

    def seen(self, item: dict[str, Any]) -> bool:
        return item["id"] in self._bucket(item["kind"])

    def retry_due(self, item_id: str) -> bool:
        record = self.failures.get(item_id)
        if not record or record.get("status") == "permanent":
            return not record
        retry = parse_time(record.get("next_retry_at", ""))
        return retry is None or retry <= utc_now()

    def success(
        self, item: dict[str, Any], topics: list[dict[str, Any]], score: float, change: str
    ) -> None:
        self._bucket(item["kind"])[item["id"]] = {
            "status": "success",
            "processed_at": utc_now().isoformat(),
            "published_at": item.get("published_at", ""),
            "content_hash": content_hash(item),
            "topics": [topic["key"] for topic in topics],
            "score": score,
            "change": change,
        }
        self.failures.pop(item["id"], None)

    def failure(self, item: dict[str, Any], error: Exception, permanent: bool = False) -> None:
        prior = self.failures.get(item["id"], {})
        attempts = int(prior.get("attempts", 0)) + 1
        delay = min(3600, 30 * (2 ** min(attempts - 1, 6)))
        self.failures[item["id"]] = {
            "item_id": item["id"],
            "source": item.get("source", ""),
            "error_type": type(error).__name__,
            "error_message": str(error)[:500],
            "first_failed_at": prior.get("first_failed_at", utc_now().isoformat()),
            "last_failed_at": utc_now().isoformat(),
            "attempts": attempts,
            "next_retry_at": (utc_now() + timedelta(seconds=delay)).isoformat(),
            "status": "permanent" if permanent else "transient",
        }

    def change_status(self, item: dict[str, Any]) -> str:
        cutoff = utc_now() - timedelta(days=int(self.settings.get("change_detection_days", 14)))
        current_tokens = set(re.findall(r"[a-z0-9]{4,}", item.get("title", "").lower()))
        for record in self.runs.get("recent_items", []):
            if (
                parse_time(record.get("processed_at", ""))
                and parse_time(record["processed_at"]) < cutoff
            ):
                continue
            previous_tokens = set(re.findall(r"[a-z0-9]{4,}", record.get("title", "").lower()))
            if len(current_tokens & previous_tokens) >= 3:
                return "UPDATED"
        return "NEW"

    def finish(self, run: dict[str, Any], items: list[dict[str, Any]]) -> None:
        retention = self.settings
        self.runs.setdefault("runs", []).append(run)
        self.runs["runs"] = self.runs["runs"][-int(retention.get("max_recent_runs", 100)) :]
        self.runs["recent_items"] = (self.runs.get("recent_items", []) + items)[
            -int(retention.get("max_processed_items", 5000)) :
        ]
        self._prune(self.videos, int(retention.get("max_processed_items", 5000)))
        self._prune(self.news, int(retention.get("max_processed_items", 5000)))
        self._prune(self.failures, int(retention.get("max_failed_items", 500)))
        for name, value in (
            ("processed_videos.json", self.videos),
            ("processed_news.json", self.news),
            ("processing_state.json", self.runs),
            ("failed_items.json", self.failures),
            ("entities.json", self.entities),
            ("events.json", self.events),
            ("trends.json", self.trends),
        ):
            self._file(name).write_text(
                json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )

    @staticmethod
    def _prune(mapping: dict[str, Any], maximum: int) -> None:
        if len(mapping) <= maximum:
            return
        for key in sorted(
            mapping,
            key=lambda item: str(
                mapping[item].get("processed_at", mapping[item].get("last_failed_at", ""))
            ),
        )[:-maximum]:
            mapping.pop(key, None)


def topic_matches(item: dict[str, Any], topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    text = f"{item.get('title', '')}\n{item.get('text', '')}".lower()
    matches = []
    for raw in topics:
        if not raw.get("enabled", True):
            continue
        terms = [str(term).lower() for term in raw.get("keywords", []) + raw.get("aliases", [])]
        found = sorted(
            {
                term
                for term in terms
                if len(term) > 1 and re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text)
            }
        )
        score = len(found) / max(1, min(4, len(terms)))
        if score >= float(raw.get("classification_threshold", 0.25)):
            matches.append(
                {
                    "key": raw.get("key", raw.get("id", raw["name"].lower().replace(" ", "-"))),
                    "name": raw["name"],
                    "score": round(score, 2),
                    "config": raw,
                    "matches": found,
                }
            )
    return sorted(
        matches,
        key=lambda match: (match["score"], match["config"].get("priority", 0)),
        reverse=True,
    )


def relevance(
    item: dict[str, Any], topics: list[dict[str, Any]], weights: dict[str, float]
) -> float:
    if not topics:
        return 0.0
    published = parse_time(item.get("published_at", ""))
    age_hours = max(0.0, (utc_now() - published).total_seconds() / 3600) if published else 72.0
    recency = max(0.0, 1 - age_hours / 168)
    completeness = min(len(item.get("text", "")) / 1500, 1.0)
    topic_score = max(topic["score"] for topic in topics)
    priority = min(float(item.get("priority", 1)) / 10, 1.0)
    return round(
        topic_score * weights.get("topic_relevance", 0.4)
        + priority * weights.get("source_priority", 0.2)
        + recency * weights.get("recency", 0.2)
        + completeness * weights.get("content_completeness", 0.2),
        3,
    )


def render(
    root: Path, stories: list[dict[str, Any]], run_time: datetime,
    micro_topic_coverage: list[dict[str, Any]] | None = None, source_health: dict[str, Any] | None = None,
    run_context: RunContext | None = None,
) -> tuple[Path, Path]:
    output = (
        PersistencePaths.for_root(root).run_dir(run_context)
        if run_context
        else root / "output" / run_time.strftime("%Y/%m/%d/%H%M")
    )
    output.mkdir(parents=True, exist_ok=True)
    from .newsletter import NewsletterModel

    newsletter = NewsletterModel.from_stories(
        stories, run_context.edition_key if run_context else run_time.isoformat(), micro_topic_coverage, source_health
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
        ("Technical Deep Dives", newsletter.technical_deep_dives),
        ("Executive Briefs", newsletter.executive_briefs),
        ("Short Summaries", newsletter.short_summaries),
        ("Flash Updates", newsletter.flash_updates),
    )
    for title, entries in sections:
        if entries:
            markdown += ["", f"## {title}"] + [f"- **{entry['title']}**: {entry.get('theme', entry.get('report_type', ''))}" for entry in entries]
    if newsletter.video_intelligence:
        markdown += ["", "## Video/Podcast Intelligence"] + [
            f"- **{story['title']}**: {story.get('theme', 'video analysis')}"
            for story in newsletter.video_intelligence
        ]
    if newsletter.opportunities:
        markdown += ["", "## Opportunities"] + [
            f"- **{opportunity.get('title', 'Opportunity')}**: {opportunity.get('recommended_action', 'Verify source details.') }"
            for opportunity in newsletter.opportunities
        ]
    if newsletter.trends:
        markdown += ["", "## Trend Signals"] + [
            f"- {trend.get('type')}: {trend.get('key')} ({trend.get('evidence_count')} evidence items)"
            for trend in newsletter.trends
        ]
    if newsletter.actions:
        markdown += ["", "## What To Watch"] + [f"- {action}" for action in newsletter.actions]
    if newsletter.sources:
        markdown += ["", "## Sources"] + [
            f"- [{source['title']}]({source['url']})" for source in newsletter.sources
        ]
    for story in stories:
        analysis = story["analysis"]
        markdown += [
            "",
            f"## {story['title']}",
            f"{story['change']} | {', '.join(topic['name'] for topic in story['topics'])} | Importance {story['importance']:.0%}",
            f"Micro-topic: {', '.join(topic['micro_topic'] for topic in story.get('micro_topics', []))} | Theme: {story.get('theme', 'unknown')} | Confidence: {story.get('confidence_score', 0):.0f}/100",
            f"Source: [{story['source']}]({story['url']})",
            "",
            "### Source Facts",
        ]
        markdown += [f"- {fact}" for fact in analysis["facts"]] or ["- No source facts extracted."]
        markdown += ["", "### AI Interpretation"] + [
            f"- {entry}" for entry in analysis["interpretation"]
        ]
        markdown += ["", "### Recommended Actions"] + [
            f"- {entry}" for entry in analysis["actionable_insights"]
        ]
    if micro_topic_coverage:
        markdown += ["", "## Micro-topic Coverage"]
        for row in micro_topic_coverage:
            markdown.append(
                f"- {row['topic']} / {row['micro_topic']}: {row['status'].replace('_', ' ')} "
                f"({row['evidence_count']} evidence items)"
            )
    if source_health:
        markdown += ["", "## Source Health"]
        markdown += [
            f"- {value['source']}: {value['status']} ({value.get('entries', 0)} entries)"
            for value in source_health.values()
        ]
    body = "\n".join(markdown) + "\n"
    cards = "".join(
        f"<tr><td style='padding:22px;border-top:1px solid #dce2e8'><span style='color:#0d6a57;font-weight:bold'>{escape(story['change'])}</span><h2 style='margin:8px 0;font-size:20px'>{escape(story['title'])}</h2><p style='color:#54616e'>{escape(', '.join(topic['name'] for topic in story['topics']))} | Micro-topic {escape(', '.join(topic['micro_topic'] for topic in story.get('micro_topics', [])))} | Importance {story['importance']:.0%} | Confidence {story.get('confidence_score', 0):.0f}/100</p><p><a href='{escape(story['url'], quote=True)}'>Open source</a></p><h3>Source facts</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in story['analysis']['facts'])}</ul><h3>AI interpretation</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in story['analysis']['interpretation'])}</ul><h3>Recommended actions</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in story['analysis']['actionable_insights'])}</ul></td></tr>"
        for story in stories
    )
    coverage_html = "".join(
        f"<li>{escape(row['topic'])} / {escape(row['micro_topic'])}: {escape(row['status'].replace('_', ' '))} ({row['evidence_count']})</li>"
        for row in (micro_topic_coverage or [])
    )
    health_html = "".join(
        f"<li>{escape(value['source'])}: {escape(value['status'])} ({value.get('entries', 0)} entries)</li>"
        for value in (source_health or {}).values()
    )
    html = f"<!doctype html><html><body style='margin:0;background:#eef2f5;font-family:Arial,sans-serif;color:#17212b'><table role='presentation' width='100%'><tr><td align='center' style='padding:24px'><table role='presentation' width='640' style='max-width:640px;background:#fff;border-collapse:collapse'><tr><td style='padding:28px;background:#102f43;color:#fff'><h1 style='margin:0'>Daily Intelligence</h1><p style='margin:8px 0 0'>{run_time:%d %b %Y} | {run_time:%H:%M UTC}</p></td></tr><tr><td style='padding:22px'><h2>Executive Brief</h2><ul>{''.join('<li>{}</li>'.format(escape(s['title'])) for s in executive) or '<li>No new high-value developments.</li>'}</ul></td></tr>{cards}<tr><td style='padding:22px'><h2>Micro-topic Coverage</h2><ul>{coverage_html or '<li>Insufficient evidence collected.</li>'}</ul><h2>Source Health</h2><ul>{health_html or '<li>No enabled sources were checked.</li>'}</ul></td></tr><tr><td style='padding:18px;background:#edf1f4;color:#5d6973;font-size:12px'>Source facts and AI interpretation are intentionally separated.</td></tr></table></td></tr></table></body></html>"
    markdown_path, html_path = output / "digest.md", output / "digest.html"
    markdown_path.write_text(body, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    return markdown_path, html_path


def run(root: Path, dry_run: bool = False, fixture_path: Path | None = None) -> tuple[Path, Path]:
    config = load_config(root)
    started = utc_now()
    paths = PersistencePaths.for_root(root)
    paths.ensure()
    edition_context, run_context = edition_context_for(config.settings, started, config.versions)
    state = RepositoryState(paths, config.settings.get("state", {}))
    pipe = config.settings["pipeline"]
    feeds = config.settings.get("news", {}).get(
        "sources", config.settings.get("news", {}).get("feeds", [])
    )
    source_health: dict[str, dict[str, Any]] = {}
    source_validation = validate_source_registry(feeds) if not fixture_path else {
        "fixture": {
            "source": "Fixture corpus", "source_id": "fixture", "enabled": True,
            "status": "HEALTHY", "item_count": 0, "usable_content_count": 0,
            "relevant_content_count": 0, "trust_tier": 1,
        }
    }
    if fixture_path:
        fixture_items = json.loads(fixture_path.read_text(encoding="utf-8"))
        discovered = []
        for index, item in enumerate(fixture_items):
            discovered.append({
                "id": item.get("id", f"fixture-{index}"), "kind": item.get("kind", "news"),
                "title": item.get("title", "Fixture item"), "url": item.get("url", "https://fixture.test/item"),
                "text": item.get("text", ""), "published_at": item.get("published_at", ""),
                "source": item.get("source", "Fixture"), "priority": item.get("priority", 8),
                "metadata": {"source_id": "fixture", "source_type": "fixture", "trust_tier": 1, "retrieved_at": started.isoformat(), **item.get("metadata", {})},
            })
        source_health["fixture"] = {"status": SourceStatus.HEALTHY.value, "entries": len(discovered), "source": "Fixture corpus", "trust_tier": 1}
        source_validation["fixture"].update({
            "item_count": len(discovered), "usable_content_count": sum(bool(item.get("title") and item.get("url")) for item in discovered),
            "relevant_content_count": len(discovered),
        })
    else:
        discovered = [
            item.to_dict()
            for item in enriched_rss(
                feeds, fetch_articles=bool(config.settings.get("news", {}).get("fetch_articles", True)),
                source_health=source_health,
            )
        ]
    if not fixture_path and os.getenv("YOUTUBE_API_KEY"):
        try:
            discovered += [
                item.to_dict()
                for item in discover_youtube(
                    config.channels,
                    config.topics,
                    os.environ["YOUTUBE_API_KEY"],
                    int(pipe.get("max_keyword_results_per_topic", 0)),
                    bool(pipe.get("allow_global_youtube_discovery", False)),
                )
            ]
        except Exception as error:  # A source/API failure must not discard RSS intelligence.
            LOGGER.warning("YouTube discovery failed: %s", type(error).__name__)
    event_groups = group_events(discovered)
    discovered = [
        {**group["items"][0], "metadata": {
            **group["items"][0].get("metadata", {}),
            "event_id": group["event_id"],
            "corroboration": group["corroboration"],
            "related_sources": group["related_sources"],
        }}
        for group in event_groups
    ]
    timestamp_status_counts: dict[str, int] = {}
    for item in discovered:
        metadata = item.setdefault("metadata", {})
        source_key = metadata.get("source_key") or metadata.get("source_id") or item.get("source", "unknown")
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
        metadata.setdefault("retrieved_at", started.isoformat())
        timestamps = source_timestamps_from_mapping(item, started)
        metadata["timestamp_status"] = timestamps.publication_status.value
        metadata["published_at_status"] = timestamps.published_at_status.value
        metadata["updated_at_status"] = timestamps.updated_at_status.value
        metadata["retrieved_at_status"] = timestamps.retrieved_at_status.value
        timestamp_status_counts[timestamps.publication_status.value] = timestamp_status_counts.get(timestamps.publication_status.value, 0) + 1
        if timestamps.published_at:
            item["published_at"] = timestamps.published_at.isoformat()
        if timestamps.updated_at:
            metadata["updated_at"] = timestamps.updated_at.isoformat()
        if timestamps.retrieved_at:
            metadata["retrieved_at"] = timestamps.retrieved_at.isoformat()
    lookback_floor = edition_context.publication_cutoff_utc - timedelta(days=int(pipe.get("lookback_days", 7)))
    publication_cutoff = edition_context.publication_cutoff_utc
    eligible = [
        item
        for item in discovered
        if eligible_for_edition(item, lookback_floor, publication_cutoff)
        and not state.seen(item)
        and state.retry_due(item["id"])
    ]
    provider = (
        DryRunProvider()
        if dry_run
        else GeminiProvider(os.environ["GEMINI_API_KEY"], config.settings["gemini"], config.prompts)
    )
    manager_settings = {
        **config.settings.get("gemini", {}),
        **config.settings.get("retrieval", {}),
        **config.settings.get("pipeline", {}),
    }
    manager = IntelligenceManager(provider, config.themes, manager_settings)
    micro_topic_catalog = catalog(config.taxonomy, config.topics, config.microtopics)
    stories, compact, coverage_assignments = [], [], []
    for item in sorted(eligible, key=lambda entry: entry.get("published_at", ""), reverse=True)[
        : int(pipe["max_items_per_run"])
    ]:
        topics = topic_matches(item, config.topics)
        micro_topics = classify_micro_topics(item, micro_topic_catalog)
        for micro_topic in micro_topics:
            if not any(topic["key"] == micro_topic["topic_key"] for topic in topics):
                topics.append({
                    "key": micro_topic["topic_key"], "name": micro_topic["topic"],
                    "score": micro_topic["confidence"], "config": {"priority": micro_topic["priority"]},
                    "matches": micro_topic["signals"],
                })
        importance = relevance(item, topics, config.settings["scoring"])
        if not topics or not micro_topics or importance < float(pipe.get("min_relevance_score", 0.35)):
            state.success(item, topics, importance, "LOW_VALUE")
            continue
        try:
            results = manager.analyze(item, micro_topics)
            for micro_topic in micro_topics:
                matched_result = next(
                    (result for result in results if result["classification"]["micro_topic"] == micro_topic["micro_topic"]),
                    None,
                )
                coverage_assignments.append({
                    **micro_topic,
                    "importance_score": event_importance(importance, item.get("metadata", {}).get("corroboration", {}).get("source_count", 1), weights=config.settings["scoring"].get("importance_weights")),
                    "evidence_available": bool(matched_result and matched_result.get("evidence")),
                    "candidate_count": int(bool(matched_result)),
                    "relevant_count": int(bool(matched_result and matched_result.get("evidence"))),
                    "event_count": int(bool(item.get("metadata", {}).get("event_id"))),
                    "publishable_count": int(bool(matched_result and matched_result.get("evidence") and matched_result.get("analysis_status") == "OK")),
                    "retrieval_status": (matched_result or {}).get("retrieval", {}).get("status", "EMPTY_RETRIEVAL"),
                    "analysis_status": (matched_result or {}).get("analysis_status", "ANALYSIS_FAILURE"),
                    "evaluation_status": (
                        "FAILED"
                        if not matched_result or (matched_result.get("retrieval", {}).get("status") == "RETRIEVAL_FAILURE") or matched_result.get("analysis_status") == "ANALYSIS_FAILURE"
                        else "EVALUATION_COMPLETE"
                    ),
                })
            if not results:
                state.success(item, topics, importance, "LOW_EVIDENCE")
                continue
            entities = extract_entities(f"{item.get('title', '')}\n{item.get('text', '')}", config.entities)
            corroboration = item.get("metadata", {}).get("corroboration", {}).get("source_count", 1)
            change = state.change_status(item)
            for result in results:
                analysis = result["analysis"]
                if not analysis or not result.get("evidence"):
                    continue
                story = {
                    **item, "topics": topics, "micro_topics": [result["classification"]],
                    "theme": result["theme"].get("id", "domain-fallback"),
                    "report_type": result["theme"].get("output", {}).get("report_type", "short_summary"),
                    "retrieved_evidence": result["evidence"], "importance": importance,
                    "importance_score": event_importance(importance, corroboration, weights=config.settings["scoring"].get("importance_weights")),
                    "confidence_score": round(confidence_score(item, analysis, corroboration) * 100),
                    "entities": entities, "opportunities": detect_opportunities(item, analysis),
                    "content_id": item.get("metadata", {}).get("content_id", ""),
                    "source_id": item.get("metadata", {}).get("source_id", ""),
                    "region": item.get("metadata", {}).get("region", "global"),
                    "country": item.get("metadata", {}).get("country", "GLOBAL"),
                    "content_type": item.get("metadata", {}).get("content_type", "news"),
                    "change": change, "analysis": analysis,
                }
                stories.append(story)
            compact.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "processed_at": utc_now().isoformat(),
                    "topics": [topic["key"] for topic in topics],
                    "content_hash": content_hash(item),
                    "content_id": item.get("metadata", {}).get("content_id", ""),
                    "source_id": item.get("metadata", {}).get("source_id", ""),
                }
            )
            state.success(item, topics, importance, change)
        except Exception as error:  # Per-item fault isolation is the pipeline's retry boundary.
            state.failure(item, error)
            LOGGER.warning("failed item %s: %s", item["id"], type(error).__name__)
    evaluation_ledger = {}
    for entry in micro_topic_catalog:
        assignments = [
            assignment for assignment in coverage_assignments
            if assignment["domain"] == entry["domain"] and assignment["micro_topic"] == entry["micro_topic"]
        ]
        key = f"{entry['domain']}:{entry['micro_topic']}"
        evaluation_ledger[key] = {
            "evaluation_status": (
                "FAILED" if any(item.get("evaluation_status") == "FAILED" for item in assignments)
                else "EVALUATION_COMPLETE" if assignments and all(item.get("evaluation_status") == "EVALUATION_COMPLETE" for item in assignments)
                else "NOT_STARTED"
            ),
            "sources_checked": len(source_health),
            "candidate_count": sum(int(item.get("candidate_count", 0)) for item in assignments),
            "relevant_count": sum(int(item.get("relevant_count", 0)) for item in assignments),
            "evidence_count": sum(int(item.get("evidence_count", 0)) for item in assignments),
        }
    source_summary = {
        "healthy_sources": sum(1 for value in source_health.values() if value["status"] == "HEALTHY"),
        "checked_sources": len(source_health),
        "evaluated_micro_topics": sorted({
            f"{assignment['domain']}:{assignment['micro_topic']}" for assignment in coverage_assignments
        }),
        "evaluation_ledger": evaluation_ledger,
    }
    micro_topic_coverage = coverage(micro_topic_catalog, coverage_assignments, source_summary)
    markdown, html = render(root, stories, started, micro_topic_coverage, source_health, run_context)
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
    for group in event_groups:
        first = group["items"][0]
        event_id = group["event_id"]
        previous = state.events.get(event_id, {})
        event_stories = [story for story in stories if story.get("metadata", {}).get("event_id") == event_id]
        state.events[event_id] = {
            "event_id": event_id,
            "first_seen": previous.get("first_seen", started.isoformat()),
            "last_seen": utc_now().isoformat(),
            "status": "UPDATED" if previous else "NEW",
            "title": first.get("title", ""),
            "entities": group.get("entities", []),
            "domains": sorted({topic.get("domain", "") for story in event_stories for topic in story.get("micro_topics", [])}),
            "topics": sorted({topic.get("key", topic.get("name", "")) for story in event_stories for topic in story.get("topics", [])}),
            "micro_topics": sorted({topic.get("micro_topic", "") for story in event_stories for topic in story.get("micro_topics", [])}),
            "sources": group.get("related_sources", []),
            "corroboration": group.get("corroboration", {}),
            "importance": max((story.get("importance_score", 0) for story in event_stories), default=0),
            "confidence": max((story.get("confidence_score", 0) for story in event_stories), default=0),
            "evidence": [entry for story in event_stories for entry in story.get("analysis", {}).get("evidence", [])],
            "related_events": previous.get("related_events", []),
        }
    for story in stories:
        for entity in story.get("entities", []):
            state.entities.setdefault(entity["name"].lower(), {"name": entity["name"], "type": entity["type"], "events": [], "first_seen": started.isoformat()})
            state.entities[entity["name"].lower()]["last_seen"] = utc_now().isoformat()
            event_id = story.get("metadata", {}).get("event_id", story["id"])
            if event_id not in state.entities[entity["name"].lower()]["events"]:
                state.entities[entity["name"].lower()]["events"].append(event_id)
    for trend in trend_signals(stories):
        state.trends[trend["type"] + ":" + trend["key"]] = {**trend, "updated_at": utc_now().isoformat()}
    state.finish(
        {
            "started": started.isoformat(),
            "completed": utc_now().isoformat(),
            "run_id": run_context.run_id,
            "edition": edition_context.edition.value,
            "edition_key": edition_context.edition_key,
            "edition_timezone": edition_context.timezone,
            "publication_cutoff_local": edition_context.publication_cutoff_local.isoformat(),
            "publication_cutoff_utc": edition_context.publication_cutoff_utc.isoformat(),
            "versions": config.versions.to_dict(),
            "timestamp_status_counts": timestamp_status_counts,
            "discovered": len(discovered),
            "eligible": len(eligible),
            "processed": len(compact),
            "micro_topic_analyses": len(stories),
            "failed": sum(1 for item in eligible if item["id"] in state.failures),
            "source_health": source_health,
            "micro_topic_coverage": micro_topic_coverage,
            "quality": quality,
            "manager_stats": manager.stats,
            "report": str(markdown.relative_to(root)),
        },
        compact,
    )
    delivery = {"status": (DeliveryStatus.SKIPPED_DRY_RUN if dry_run else DeliveryStatus.DISABLED).value, "updated_at": utc_now().isoformat()}
    paths.data_file("source_validation.json").write_text(
        json.dumps(source_validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if config.settings.get("email", {}).get("enabled") and not dry_run and quality["passed"]:
        try:
            send_digest(
                html,
                markdown,
                f"{config.settings['email'].get('subject_prefix', 'Daily Intelligence')} - {started:%d %b %Y %H:%M}",
            )
            delivery = {"status": DeliveryStatus.DELIVERY_CONFIRMED.value, "updated_at": utc_now().isoformat()}
        except Exception as error:  # Delivery failure is recorded by logs after report/state persistence.
            LOGGER.warning("SMTP delivery failed: %s", type(error).__name__)
            delivery = {"status": DeliveryStatus.DELIVERY_FAILED.value, "error_type": type(error).__name__, "updated_at": utc_now().isoformat()}
    elif not dry_run and not quality["passed"]:
        delivery = {"status": DeliveryStatus.QUALITY_REVIEW_REQUIRED.value, "updated_at": utc_now().isoformat()}
    paths.data_file("delivery_state.json").write_text(
        json.dumps(delivery, indent=2) + "\n", encoding="utf-8"
    )
    return markdown, html
