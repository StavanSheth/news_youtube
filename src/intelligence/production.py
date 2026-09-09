from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import UTC, datetime, timedelta
from html import escape
from pathlib import Path
from typing import Any

from .config import load_config
from .emailer import send_digest
from .events import group_events
from .events import importance as event_importance
from .ingestion import enriched_rss
from .schema import merge_unique, normalized_analysis
from .sources import discover_youtube

LOGGER = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


def parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def content_hash(item: dict[str, Any]) -> str:
    text = "\n".join((item.get("title", ""), item.get("text", ""), item.get("url", "")))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


class RepositoryState:
    """Compact, versioned repository-file state with retry and retention controls."""

    def __init__(self, data_dir: Path, settings: dict[str, Any]) -> None:
        self.data_dir, self.settings = data_dir, settings
        self.videos = self._read("processed_videos.json", {})
        self.news = self._read("processed_news.json", {})
        self.runs = self._read("processing_state.json", {"runs": [], "recent_items": []})
        self.failures = self._read("failed_items.json", {})

    def _read(self, name: str, fallback: Any) -> Any:
        try:
            return json.loads((self.data_dir / name).read_text(encoding="utf-8"))
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
        ):
            (self.data_dir / name).write_text(
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


class GeminiProvider:
    def __init__(self, key: str, config: dict[str, Any], prompts: dict[str, str]) -> None:
        from google import genai

        self.client, self.config, self.prompts = genai.Client(api_key=key), config, prompts

    def analyze(self, item: dict[str, Any], topic: dict[str, Any]) -> dict[str, Any]:
        size = int(self.config.get("chunk_size", 9000))
        overlap = int(self.config.get("chunk_overlap", 500))
        text = item.get("text", "")
        chunks = [
            text[index : index + size]
            for index in range(0, max(len(text), 1), max(1, size - overlap))
        ][: int(self.config.get("max_chunks_per_item", 6))]
        extracted = [
            self._request(f"{self.prompts['chunk_extraction']}\n\nSOURCE:\n{chunk}")
            for chunk in chunks
        ]
        facts = merge_unique(entry["facts"] for entry in extracted)
        details = json.dumps(
            {
                "topic": topic["config"],
                "facts": facts,
                "source": {key: item.get(key) for key in ("title", "url", "source")},
                "related_sources": item.get("metadata", {}).get("related_sources", []),
            }
        )
        result = self._request(f"{self.prompts['topic_analysis']}\n\nINPUT:\n{details}")
        result["facts"] = merge_unique((facts, result["facts"]))
        return result

    def _request(self, prompt: str) -> dict[str, Any]:
        response = self.client.models.generate_content(
            model=self.config["model"],
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "temperature": self.config.get("temperature", 0.2),
                "max_output_tokens": self.config.get("max_output_tokens", 4096),
            },
        )
        return normalized_analysis(json.loads(response.text))


def render(root: Path, stories: list[dict[str, Any]], run_time: datetime) -> tuple[Path, Path]:
    output = root / "output" / run_time.strftime("%Y/%m/%d/%H%M")
    output.mkdir(parents=True, exist_ok=True)
    from .newsletter import NewsletterModel

    executive = NewsletterModel.from_stories(stories, run_time.isoformat()).executive_summary
    markdown = [
        "# Daily Intelligence",
        f"**Edition:** {run_time:%Y-%m-%d %H:%M UTC}",
        "",
        "## Executive Brief",
    ]
    markdown += [
        f"- **{story['title']}** ({story['change']}, {story['importance']:.0%})"
        for story in executive
    ] or ["- No new high-value developments."]
    for story in stories:
        analysis = story["analysis"]
        markdown += [
            "",
            f"## {story['title']}",
            f"{story['change']} | {', '.join(topic['name'] for topic in story['topics'])} | Importance {story['importance']:.0%}",
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
    body = "\n".join(markdown) + "\n"
    cards = "".join(
        f"<tr><td style='padding:22px;border-top:1px solid #dce2e8'><span style='color:#0d6a57;font-weight:bold'>{escape(story['change'])}</span><h2 style='margin:8px 0;font-size:20px'>{escape(story['title'])}</h2><p style='color:#54616e'>{escape(', '.join(topic['name'] for topic in story['topics']))} | Importance {story['importance']:.0%}</p><p><a href='{escape(story['url'], quote=True)}'>Open source</a></p><h3>Source facts</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in story['analysis']['facts'])}</ul><h3>AI interpretation</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in story['analysis']['interpretation'])}</ul><h3>Recommended actions</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in story['analysis']['actionable_insights'])}</ul></td></tr>"
        for story in stories
    )
    html = f"<!doctype html><html><body style='margin:0;background:#eef2f5;font-family:Arial,sans-serif;color:#17212b'><table role='presentation' width='100%'><tr><td align='center' style='padding:24px'><table role='presentation' width='640' style='max-width:640px;background:#fff;border-collapse:collapse'><tr><td style='padding:28px;background:#102f43;color:#fff'><h1 style='margin:0'>Daily Intelligence</h1><p style='margin:8px 0 0'>{run_time:%d %b %Y} | {run_time:%H:%M UTC}</p></td></tr><tr><td style='padding:22px'><h2>Executive Brief</h2><ul>{''.join('<li>{}</li>'.format(escape(s['title'])) for s in executive) or '<li>No new high-value developments.</li>'}</ul></td></tr>{cards}<tr><td style='padding:18px;background:#edf1f4;color:#5d6973;font-size:12px'>Source facts and AI interpretation are intentionally separated.</td></tr></table></td></tr></table></body></html>"
    markdown_path, html_path = output / "digest.md", output / "digest.html"
    markdown_path.write_text(body, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    return markdown_path, html_path


def run(root: Path, dry_run: bool = False) -> tuple[Path, Path]:
    config = load_config(root)
    started = utc_now()
    state = RepositoryState(root / "data", config.settings.get("state", {}))
    pipe = config.settings["pipeline"]
    feeds = config.settings.get("news", {}).get(
        "sources", config.settings.get("news", {}).get("feeds", [])
    )
    discovered = [
        item.to_dict()
        for item in enriched_rss(
            feeds, fetch_articles=bool(config.settings.get("news", {}).get("fetch_articles", True))
        )
    ]
    if os.getenv("YOUTUBE_API_KEY"):
        discovered += [
            item.to_dict()
            for item in discover_youtube(
                config.channels,
                config.topics,
                os.environ["YOUTUBE_API_KEY"],
                int(pipe.get("max_keyword_results_per_topic", 0)),
            )
        ]
    cutoff = utc_now() - timedelta(days=int(pipe.get("lookback_days", 7)))
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
    eligible = [
        item
        for item in discovered
        if (
            not parse_time(item.get("published_at", ""))
            or parse_time(item["published_at"]) >= cutoff
        )
        and not state.seen(item)
        and state.retry_due(item["id"])
    ]
    provider = (
        None
        if dry_run
        else GeminiProvider(os.environ["GEMINI_API_KEY"], config.settings["gemini"], config.prompts)
    )
    stories, compact = [], []
    for item in sorted(eligible, key=lambda entry: entry.get("published_at", ""), reverse=True)[
        : int(pipe["max_items_per_run"])
    ]:
        topics = topic_matches(item, config.topics)
        importance = relevance(item, topics, config.settings["scoring"])
        if not topics or importance < float(pipe.get("min_relevance_score", 0.35)):
            state.success(item, topics, importance, "LOW_VALUE")
            continue
        try:
            analysis = (
                {
                    "facts": ["Dry-run fixture analysis."],
                    "important_numbers": [],
                    "claims": [],
                    "interpretation": [],
                    "changes": [],
                    "implications": [],
                    "risks": [],
                    "opportunities": [],
                    "actionable_insights": [],
                    "routine": None,
                    "uncertainties": [],
                    "confidence": 0.0,
                }
                if dry_run
                else provider.analyze(item, {**topics[0], "theme": next((theme for theme in config.themes if theme.get("topic") == topics[0]["name"]), {})})
            )
            change = state.change_status(item)
            story = {
                **item,
                "topics": topics,
                "importance": importance,
                "importance_score": event_importance(
                    importance,
                    item.get("metadata", {}).get("corroboration", {}).get("source_count", 1),
                ),
                "change": change,
                "analysis": analysis,
            }
            stories.append(story)
            compact.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "processed_at": utc_now().isoformat(),
                    "topics": [topic["key"] for topic in topics],
                    "content_hash": content_hash(item),
                }
            )
            state.success(item, topics, importance, change)
        except Exception as error:  # Per-item fault isolation is the pipeline's retry boundary.
            state.failure(item, error)
            LOGGER.warning("failed item %s: %s", item["id"], type(error).__name__)
    markdown, html = render(root, stories, started)
    state.finish(
        {
            "started": started.isoformat(),
            "completed": utc_now().isoformat(),
            "discovered": len(discovered),
            "eligible": len(eligible),
            "processed": len(stories),
            "failed": sum(1 for item in eligible if item["id"] in state.failures),
            "report": str(markdown.relative_to(root)),
        },
        compact,
    )
    if config.settings.get("email", {}).get("enabled") and not dry_run:
        send_digest(
            html,
            markdown,
            f"{config.settings['email'].get('subject_prefix', 'Daily Intelligence')} - {started:%d %b %Y %H:%M}",
        )
    return markdown, html
