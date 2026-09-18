"""Authoritative repository state management.

RepositoryState is the single source of truth for persistent state
(processed items, failures, entity/event/trend tracking, retention).
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .infrastructure.clock import now_utc
from .persistence import PersistencePaths


def _parse_time(value: str) -> datetime | None:
    """Parse an ISO-format time string, handling missing timezone."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def _content_hash(item: dict[str, Any]) -> str:
    """Deterministic hash of item content for change detection."""
    text = "\n".join((item.get("title", ""), item.get("text", ""), item.get("url", "")))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


class RepositoryState:
    """Compact, versioned repository-file state with retry and retention controls."""

    def __init__(self, paths: PersistencePaths | Path, settings: dict[str, Any] | None = None) -> None:
        self.paths = paths if isinstance(paths, PersistencePaths) else None
        self.data_dir = paths.data if self.paths else paths
        self.settings = settings or {}
        self.videos = self._read("processed_videos.json", {})
        self.news = self._read("processed_news.json", {})
        self.runs = self._read("processing_state.json", {"runs": [], "recent_items": []})
        self.failures = self._read("failed_items.json", {})
        self.entities = self._read("entities.json", {})
        self.events = self._read("events.json", {})
        self.trends = self._read("trends.json", {})

    def _file(self, name: str) -> Path:
        if self.paths:
            if name in {
                "processed_videos.json",
                "processed_news.json",
                "processing_state.json",
                "failed_items.json",
            }:
                target = self.paths.state / name
            elif name == "entities.json":
                target = self.paths.entities / name
            elif name == "events.json":
                target = self.paths.events / name
            elif name == "trends.json":
                target = self.paths.state / name
            else:
                target = self.paths.data_file(name)
            legacy = self.paths.data_file(name)
            if not target.exists() and legacy.exists():
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(legacy.read_bytes())
                except OSError:
                    return legacy
            return target
        return self.data_dir / name

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
        retry = _parse_time(record.get("next_retry_at", ""))
        return retry is None or retry <= now_utc()

    def success(
        self,
        item: dict[str, Any],
        topics_or_analysis: list[dict[str, Any]] | dict[str, Any] | None = None,
        score: float = 0.0,
        change: str = "NEW",
    ) -> None:
        """Record a successful processing result.

        Supports two calling conventions:
        - New (RepositoryState): success(item, topics_list, score, change)
        - Legacy (StateStore):   success(item, analysis_dict)
        """
        if isinstance(topics_or_analysis, dict):
            # Legacy StateStore convention: success(item, analysis)
            bucket = self.videos if item["kind"] == "youtube" else self.news
            bucket[item["id"]] = {
                "processed_at": now_utc().isoformat(),
                "analysis": topics_or_analysis,
            }
            self.failures.pop(item["id"], None)
        else:
            # New RepositoryState convention: success(item, topics, score, change)
            topics = topics_or_analysis or []
            self._bucket(item["kind"])[item["id"]] = {
                "status": "success",
                "processed_at": now_utc().isoformat(),
                "published_at": item.get("published_at", ""),
                "content_hash": _content_hash(item),
                "topics": [topic["key"] for topic in topics],
                "score": score,
                "change": change,
            }
            self.failures.pop(item["id"], None)

    def failure(
        self,
        item_or_id: dict[str, Any] | str,
        error: Exception,
        permanent: bool = False,
    ) -> None:
        """Record a processing failure.

        Supports two calling conventions:
        - New (RepositoryState): failure(item_dict, error, permanent)
        - Legacy (StateStore):   failure(item_id_str, error)
        """
        if isinstance(item_or_id, str):
            # Legacy StateStore convention
            item_id = item_or_id
            prior = self.failures.get(item_id, {})
            self.failures[item_id] = {
                "attempts": prior.get("attempts", 0) + 1,
                "last_error": str(error)[:1000],
                "last_attempt": now_utc().isoformat(),
            }
        else:
            # New RepositoryState convention
            item = item_or_id
            prior = self.failures.get(item["id"], {})
            attempts = int(prior.get("attempts", 0)) + 1
            delay = min(3600, 30 * (2 ** min(attempts - 1, 6)))
            self.failures[item["id"]] = {
                "item_id": item["id"],
                "source": item.get("source", ""),
                "error_type": type(error).__name__,
                "error_message": str(error)[:500],
                "first_failed_at": prior.get("first_failed_at", now_utc().isoformat()),
                "last_failed_at": now_utc().isoformat(),
                "attempts": attempts,
                "next_retry_at": (now_utc() + timedelta(seconds=delay)).isoformat(),
                "status": "permanent" if permanent else "transient",
            }

    def change_status(self, item: dict[str, Any]) -> str:
        cutoff = now_utc() - timedelta(days=int(self.settings.get("change_detection_days", 14)))
        current_tokens = set(re.findall(r"[a-z0-9]{4,}", item.get("title", "").lower()))
        for record in self.runs.get("recent_items", []):
            ts = _parse_time(record.get("processed_at", ""))
            if ts and ts < cutoff:
                continue
            previous_tokens = set(re.findall(r"[a-z0-9]{4,}", record.get("title", "").lower()))
            if len(current_tokens & previous_tokens) >= 3:
                return "UPDATED"
        return "NEW"

    def finish(self, run: dict[str, Any], items: list[dict[str, Any]]) -> None:
        retention = self.settings
        self.runs.setdefault("runs", []).append(run)
        self.runs["runs"] = self.runs["runs"][-int(retention.get("max_recent_runs", 100)):]
        self.runs["recent_items"] = (self.runs.get("recent_items", []) + items)[
            -int(retention.get("max_processed_items", 5000)):
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
                json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
            )

    # --- Legacy convenience API (backward compatibility for StateStore callers) ---

    def is_processed(self, item_id: str, kind: str) -> bool:
        return item_id in (self.videos if kind == "youtube" else self.news)

    def record_run(self, run: dict[str, Any], history_limit: int) -> None:
        self.runs.setdefault("runs", []).append(run)
        self.runs["runs"] = self.runs["runs"][-100:]
        self.runs["recent_items"] = (
            self.runs.get("recent_items", []) + run.get("items", [])
        )[-history_limit:]

    def save(self) -> None:
        for name, payload in (
            ("processed_videos.json", self.videos),
            ("processed_news.json", self.news),
            ("processing_state.json", self.runs),
            ("failed_items.json", self.failures),
            ("entities.json", self.entities),
            ("events.json", self.events),
            ("trends.json", self.trends),
        ):
            self._file(name).write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
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


# Backward compatibility alias: old code using StateStore keeps working
StateStore = RepositoryState
