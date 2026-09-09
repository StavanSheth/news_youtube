from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NewsletterModel:
    """Canonical report model shared by Markdown and HTML renderers."""

    edition: str
    executive_summary: list[dict[str, Any]] = field(default_factory=list)
    stories: list[dict[str, Any]] = field(default_factory=list)
    opportunities: list[dict[str, Any]] = field(default_factory=list)
    trends: list[dict[str, Any]] = field(default_factory=list)
    watch_items: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    sources: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def from_stories(cls, stories: list[dict[str, Any]], edition: str) -> "NewsletterModel":
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
        return cls(
            edition=edition,
            executive_summary=executive,
            stories=stories,
            opportunities=opportunities,
            trends=trend_signals(stories),
            actions=actions,
            sources=sources,
        )
