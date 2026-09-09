from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class StateStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.processed_videos = self._read("processed_videos.json", {})
        self.processed_news = self._read("processed_news.json", {})
        self.processing = self._read("processing_state.json", {"runs": [], "recent_items": []})
        self.failures = self._read("failed_items.json", {})

    def _read(self, name: str, default: Any) -> Any:
        path = self.data_dir / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

    def is_processed(self, item_id: str, kind: str) -> bool:
        return item_id in (self.processed_videos if kind == "youtube" else self.processed_news)

    def success(self, item: dict[str, Any], analysis: dict[str, Any]) -> None:
        bucket = self.processed_videos if item["kind"] == "youtube" else self.processed_news
        bucket[item["id"]] = {"processed_at": datetime.now(UTC).isoformat(), "analysis": analysis}
        self.failures.pop(item["id"], None)

    def failure(self, item_id: str, error: Exception) -> None:
        previous = self.failures.get(item_id, {})
        self.failures[item_id] = {
            "attempts": previous.get("attempts", 0) + 1,
            "last_error": str(error)[:1000],
            "last_attempt": datetime.now(UTC).isoformat(),
        }

    def record_run(self, run: dict[str, Any], history_limit: int) -> None:
        self.processing.setdefault("runs", []).append(run)
        self.processing["runs"] = self.processing["runs"][-100:]
        self.processing["recent_items"] = (
            self.processing.get("recent_items", []) + run.get("items", [])
        )[-history_limit:]

    def save(self) -> None:
        for name, payload in (
            ("processed_videos.json", self.processed_videos),
            ("processed_news.json", self.processed_news),
            ("processing_state.json", self.processing),
            ("failed_items.json", self.failures),
        ):
            (self.data_dir / name).write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
