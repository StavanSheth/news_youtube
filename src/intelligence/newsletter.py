from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NewsletterModel:
    """Canonical report model shared by Markdown and HTML renderers."""

    edition: str
    executive_summary: list[dict[str, Any]] = field(default_factory=list)
    top_events: list[dict[str, Any]] = field(default_factory=list)
    news_intelligence: list[dict[str, Any]] = field(default_factory=list)
    video_intelligence: list[dict[str, Any]] = field(default_factory=list)
    case_studies: list[dict[str, Any]] = field(default_factory=list)
    technical_deep_dives: list[dict[str, Any]] = field(default_factory=list)
    executive_briefs: list[dict[str, Any]] = field(default_factory=list)
    short_summaries: list[dict[str, Any]] = field(default_factory=list)
    flash_updates: list[dict[str, Any]] = field(default_factory=list)
    stories: list[dict[str, Any]] = field(default_factory=list)
    opportunities: list[dict[str, Any]] = field(default_factory=list)
    trends: list[dict[str, Any]] = field(default_factory=list)
    watch_items: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    sources: list[dict[str, str]] = field(default_factory=list)
    micro_topic_coverage: list[dict[str, Any]] = field(default_factory=list)
    source_health: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_stories(
        cls,
        stories: list[dict[str, Any]],
        edition: str,
        micro_topic_coverage: list[dict[str, Any]] | None = None,
        source_health: dict[str, Any] | None = None,
    ) -> "NewsletterModel":
        from .enrichment import trend_signals

        executive = sorted(
            stories,
            key=lambda story: story.get("importance_score", story.get("importance", 0)),
            reverse=True,
        )[:7]
        actions = list(dict.fromkeys(
            insight
            for story in stories
            for insight in story.get("analysis", {}).get("actionable_insights", [])
        ))
        sources = [
            {"title": story.get("title", ""), "url": story.get("url", "")}
            for story in stories if story.get("url")
        ]
        opportunities = [opportunity for story in stories for opportunity in story.get("opportunities", [])]
        top_events = [story for story in executive if story.get("importance_score", 0) >= 70]
        news = [story for story in stories if story.get("kind") != "youtube"]
        videos = [story for story in stories if story.get("kind") == "youtube"]
        grouped = {
            "case_studies": [story for story in stories if story.get("report_type") == "case_study"],
            "technical_deep_dives": [story for story in stories if story.get("report_type") == "technical_deep_dive"],
            "executive_briefs": [story for story in stories if story.get("report_type") == "executive_brief"],
            "short_summaries": [story for story in stories if story.get("report_type") == "short_summary"],
            "flash_updates": [story for story in stories if story.get("report_type") == "flash_update"],
        }
        return cls(
            edition=edition,
            executive_summary=executive,
            top_events=top_events,
            news_intelligence=news,
            video_intelligence=videos,
            **grouped,
            stories=stories,
            opportunities=opportunities,
            trends=trend_signals(stories),
            actions=actions,
            sources=sources,
            micro_topic_coverage=micro_topic_coverage or [],
            source_health=list((source_health or {}).values()),
        )
