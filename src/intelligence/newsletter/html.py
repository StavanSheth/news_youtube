"""Independent HTML renderer consuming NewsletterModel."""

from __future__ import annotations

from html import escape

from .model import NewsletterModel

DEFAULT_HTML_SHELL = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Intelligence Digest - {{EDITION}}</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1a1a1a; max-width: 800px; margin: 0 auto; padding: 24px; }
article { border-bottom: 1px solid #e5e5e5; padding-bottom: 24px; margin-bottom: 24px; }
h1, h2, h3, h4 { color: #111; }
.meta { color: #666; font-size: 0.9em; }
ul { padding-left: 20px; }
a { color: #0066cc; text-decoration: none; }
a:hover { text-decoration: underline; }
</style>
</head>
<body>
<h1>Intelligence Digest</h1>
<p class="meta">Edition: {{EDITION}}</p>
{{CONTENT}}
</body>
</html>"""


def render_html(model: NewsletterModel, template_str: str | None = None) -> str:
    """Render canonical NewsletterModel as HTML."""
    shell = template_str or DEFAULT_HTML_SHELL
    cards: list[str] = []

    for story in model.stories:
        title = story.get("title", "Untitled")
        source = story.get("source", "Unknown")
        url = story.get("url", "")
        score = story.get("importance_score", story.get("importance", 0))
        topics = story.get("topics", [])
        analysis = story.get("analysis", {})

        def _format_section(heading: str, items: list[str]) -> str:
            if not items:
                return ""
            li_tags = "".join(f"<li>{escape(str(item))}</li>" for item in items)
            return f"<h4>{escape(heading)}</h4><ul>{li_tags}</ul>"

        facts_html = _format_section("Verified Facts", analysis.get("facts", []))
        interp_html = _format_section("AI Interpretation", analysis.get("interpretation", []))
        insights_html = _format_section("Actionable Insights", analysis.get("actionable_insights", []))

        source_link = f"<a href='{escape(url, quote=True)}'>{escape(source)}</a>" if url else escape(source)
        cards.append(
            f"<article>"
            f"<h3>{escape(title)}</h3>"
            f"<p class='meta'>{source_link} | {escape(', '.join(topics))} | Score: {score}</p>"
            f"{facts_html}{interp_html}{insights_html}"
            f"</article>"
        )

    content = "\n".join(cards) if cards else "<p>No new high-relevance intelligence this run.</p>"

    return (
        shell.replace("{{EDITION}}", escape(model.edition))
        .replace("{{CONTENT}}", content)
    )
