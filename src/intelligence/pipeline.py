from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from .ai import GeminiAnalyzer
from .classification import classify, relevance_score
from .config import load_config
from .emailer import send_digest
from .models import Analysis
from .render import write_reports
from .sources import discover_rss, discover_youtube
from .state import StateStore


def run(root: Path, dry_run: bool = False) -> tuple[Path, Path]:
    config = load_config(root)
    state = StateStore(root / "data")
    pipe = config.settings["pipeline"]
    now = datetime.now().astimezone()
    discovered = list(discover_rss(config.settings.get("news", {}).get("feeds", [])))
    if os.getenv("YOUTUBE_API_KEY"):
        discovered += list(
            discover_youtube(
                config.channels,
                config.topics,
                os.environ["YOUTUBE_API_KEY"],
                pipe["max_keyword_results_per_topic"],
            )
        )
    analyzer = (
        None
        if dry_run
        else GeminiAnalyzer(
            os.environ["GEMINI_API_KEY"],
            config.prompts,
            pipe["chunk_size"],
            pipe["max_chunks_per_item"],
        )
    )
    results = []
    for item in discovered[: pipe["max_items_per_run"]]:
        if state.is_processed(item.id, item.kind):
            continue
        try:
            matches = classify(f"{item.title}\n{item.text}", config.topics)
            score = relevance_score(item, matches, config.settings["scoring"])
            if score < pipe["min_relevance_score"]:
                state.success(item.to_dict(), {"status": "low_relevance", "score": score})
                continue
            topic_names = [entry["topic"]["name"] for entry in matches]
            if dry_run:
                analysis = {
                    "facts": ["Dry-run: source was classified without external AI."],
                    "interpretation": [],
                    "actionable_insights": [],
                    "routine": None,
                    "uncertainties": [],
                }
            else:
                # The highest matching topic directs deep analysis; classification remains multi-topic.
                analysis = analyzer.analyze(
                    item, max(matches, key=lambda entry: entry["coverage"])["topic"]
                )
            record = Analysis(
                item,
                topic_names,
                score,
                analysis.get("facts", []),
                analysis.get("interpretation", []),
                analysis.get("actionable_insights", []),
                analysis.get("routine"),
                analysis.get("uncertainties", []),
            ).to_dict()
            state.success(item.to_dict(), record)
            results.append(record)
        except Exception as error:
            state.failure(item.id, error)
    markdown, html = write_reports(root, results, now)
    state.record_run(
        {"at": now.isoformat(), "items": results, "report": str(markdown.relative_to(root))},
        pipe["retain_history"],
    )
    state.save()
    if config.settings.get("email", {}).get("enabled") and not dry_run:
        send_digest(
            html,
            markdown,
            f"{config.settings['email'].get('subject_prefix', 'Intelligence Digest')} - {now:%Y-%m-%d %H:%M}",
        )
    return markdown, html
