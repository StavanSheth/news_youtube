"""Independent Markdown renderer consuming NewsletterModel."""

from __future__ import annotations

from .model import NewsletterModel


def render_markdown(model: NewsletterModel) -> str:
    """Render canonical NewsletterModel as formatted Markdown."""
    lines: list[str] = [
        "# Intelligence Digest",
        f"**Edition:** {model.edition}",
        "",
    ]

    # Executive summary
    if model.executive_summary:
        lines.append("## Executive Summary")
        for story in model.executive_summary:
            title = story.get("title", "Untitled")
            source = story.get("source", "Unknown")
            url = story.get("url", "")
            score = story.get("importance_score", story.get("importance", 0))
            link = f"[{source}]({url})" if url else source
            lines.append(f"- **{title}** ({link} | Score: {score})")
        lines.append("")

    # Stories
    if model.stories:
        lines.append("## Analyzed Intelligence")
        for story in model.stories:
            title = story.get("title", "Untitled")
            source = story.get("source", "Unknown")
            url = story.get("url", "")
            score = story.get("importance_score", story.get("importance", 0))
            topics = story.get("topics", [])
            analysis = story.get("analysis", {})

            link = f"[{source}]({url})" if url else source
            lines.append(f"### {title}")
            lines.append(f"Source: {link} | Score: {score} | Topics: {', '.join(topics)}")
            lines.append("")

            # Facts
            facts = analysis.get("facts", [])
            lines.append("#### Verified Facts")
            if facts:
                for f in facts:
                    lines.append(f"- {f}")
            else:
                lines.append("- No supported facts extracted.")
            lines.append("")

            # Interpretation
            interpretation = analysis.get("interpretation", [])
            if interpretation:
                lines.append("#### AI Interpretation")
                for item in interpretation:
                    lines.append(f"- {item}")
                lines.append("")

            # Actionable insights
            insights = analysis.get("actionable_insights", [])
            if insights:
                lines.append("#### Actionable Insights")
                for item in insights:
                    lines.append(f"- {item}")
                lines.append("")

    # Global Action items
    if model.actions:
        lines.append("## Actionable Insights & Next Steps")
        for action in model.actions:
            lines.append(f"- {action}")
        lines.append("")

    # Sources
    if model.sources:
        lines.append("## Cited Sources")
        for src in model.sources:
            lines.append(f"- [{src.get('title', 'Source')}]({src.get('url', '')})")
        lines.append("")

    return "\n".join(lines)
