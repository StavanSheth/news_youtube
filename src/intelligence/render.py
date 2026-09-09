from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path


def markdown_digest(analyses: list[dict], run_time: datetime) -> str:
    lines = ["# Intelligence Digest", f"**Edition:** {run_time:%Y-%m-%d %H:%M %Z}", ""]
    for analysis in analyses:
        item = analysis["item"]
        lines += [
            f"## {item['title']}",
            f"Source: [{item['source']}]({item['url']}) | Score: {analysis['score']}",
            f"Topics: {', '.join(analysis['topics'])}",
            "",
            "### Source facts",
        ]
        lines += [f"- {entry}" for entry in analysis["facts"]] or [
            "- No supported facts extracted."
        ]
        lines += ["", "### AI interpretation"] + [
            f"- {entry}" for entry in analysis["interpretation"]
        ]
        lines += ["", "### Actionable insights"] + [
            f"- {entry}" for entry in analysis["actionable_insights"]
        ]
        if analysis.get("routine"):
            lines.append("\n### Routine/workflow")
            for period, actions in analysis["routine"].items():
                lines += [f"**{period}**"] + [f"- {action}" for action in actions]
        lines.append("")
    return "\n".join(lines)


def html_digest(analyses: list[dict], run_time: datetime, template: str) -> str:
    cards = []
    for analysis in analyses:
        item = analysis["item"]

        def listing(title: str, entries: list[str]) -> str:
            return (
                f"<h3>{escape(title)}</h3><ul>{''.join(f'<li>{escape(str(x))}</li>' for x in entries)}</ul>"
                if entries
                else ""
            )

        routine = "".join(
            f"<h3>{escape(period)}</h3><ul>{''.join(f'<li>{escape(str(a))}</li>' for a in actions)}</ul>"
            for period, actions in (analysis.get("routine") or {}).items()
        )
        cards.append(
            f"<article><h2>{escape(item['title'])}</h2><p class='meta'>{escape(item['source'])} | {escape(', '.join(analysis['topics']))} | Score {analysis['score']}</p><p><a href='{escape(item['url'], quote=True)}'>Read or watch source</a></p>{listing('Source facts', analysis['facts'])}{listing('AI interpretation', analysis['interpretation'])}{listing('Actionable insights', analysis['actionable_insights'])}{routine}</article>"
        )
    return (
        template.replace("{{DATE}}", run_time.strftime("%d %b %Y"))
        .replace("{{EDITION}}", run_time.strftime("%H:%M %Z"))
        .replace(
            "{{CONTENT}}", "\n".join(cards) or "<p>No new high-relevance content this run.</p>"
        )
    )


def write_reports(root: Path, analyses: list[dict], run_time: datetime) -> tuple[Path, Path]:
    output = root / "output" / run_time.strftime("%Y/%m/%d/%H%M")
    output.mkdir(parents=True, exist_ok=True)
    markdown = output / "digest.md"
    html = output / "digest.html"
    markdown.write_text(markdown_digest(analyses, run_time), encoding="utf-8")
    html.write_text(
        html_digest(
            analyses, run_time, (root / "templates/newsletter.html").read_text(encoding="utf-8")
        ),
        encoding="utf-8",
    )
    return markdown, html
