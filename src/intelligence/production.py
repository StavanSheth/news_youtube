from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, time
from html import escape
from pathlib import Path
from typing import Any

from .classification import relevance, topic_matches
from .contracts import EditionType, RunContext, TimestampStatus, build_edition_context, source_timestamps_from_mapping
from .persistence import PersistencePaths
from .state import RepositoryState
from zoneinfo import ZoneInfo

__all__ = [
    "RepositoryState",
    "eligible_for_edition",
    "relevance",
    "render",
    "run",
    "topic_matches",
]

LOGGER = logging.getLogger(__name__)


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
    """Execute authoritative production pipeline using ApplicationOrchestrator."""
    from .application.orchestrator import ApplicationOrchestrator

    orchestrator = ApplicationOrchestrator(root, dry_run=dry_run, fixture_path=fixture_path)
    return orchestrator.run_edition()

