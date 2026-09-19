"""YouTube Data API v3 client implementing the configured-channel uploads playlist flow."""

from __future__ import annotations

import logging
from typing import Any


from ..base import SafeHttpClient
from .quota import YouTubeQuotaTracker, default_quota_tracker

LOGGER = logging.getLogger(__name__)


class YouTubeClient:
    """YouTube API client executing configured-channel-only collection with quota safety."""

    BASE_URL = "https://www.googleapis.com/youtube/v3"

    def __init__(
        self,
        api_key: str,
        quota_tracker: YouTubeQuotaTracker | None = None,
        http_client: SafeHttpClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.quota_tracker = quota_tracker or default_quota_tracker
        self.http_client = http_client or SafeHttpClient(default_timeout=15)

    def _get(self, endpoint: str, params: dict[str, Any], units: int = 1) -> dict[str, Any]:
        """Execute YouTube API GET request with quota protection, reservation, and circuit breaker."""
        if not self.api_key:
            raise ValueError("YouTube API key is missing")

        if self.quota_tracker.circuit_breaker_tripped:
            raise RuntimeError("YouTube API circuit breaker tripped due to repeated failures")

        if not self.quota_tracker.reserve(units):
            self.quota_tracker.record_failure(is_quota_exceeded=True)
            raise RuntimeError("YouTube API quota limit exceeded for this run")

        url = f"{self.BASE_URL}/{endpoint}"
        query_params = {**params, "key": self.api_key}

        try:
            response = self.http_client.get(url, params=query_params)

            if response.status_code == 403:
                error_data = response.json() if response.content else {}
                reasons = [e.get("reason", "") for e in error_data.get("error", {}).get("errors", [])]
                is_quota = "quotaExceeded" in reasons or "dailyLimitExceeded" in reasons
                self.quota_tracker.release(units)
                self.quota_tracker.record_failure(is_quota_exceeded=is_quota)
                response.raise_for_status()

            if response.status_code == 429:
                self.quota_tracker.release(units)
                self.quota_tracker.record_failure(is_rate_limit=True, is_429=True)
                response.raise_for_status()

            response.raise_for_status()
            self.quota_tracker.consume(units=units)
            return response.json()

        except Exception as exc:
            self.quota_tracker.release(units)
            self.quota_tracker.record_failure()
            raise exc

    def get_channel_uploads_playlist(self, channel_id: str) -> str | None:
        """Retrieve uploads playlist ID for a configured channel (1 unit)."""
        data = self._get("channels", {"part": "contentDetails", "id": channel_id}, units=1)
        items = data.get("items", [])
        if not items:
            return None
        return (
            items[0]
            .get("contentDetails", {})
            .get("relatedPlaylists", {})
            .get("uploads")
        )

    def get_playlist_items(self, playlist_id: str, max_results: int = 15) -> list[dict[str, Any]]:
        """Retrieve video references from uploads playlist (1 unit)."""
        data = self._get(
            "playlistItems",
            {"part": "snippet,contentDetails", "playlistId": playlist_id, "maxResults": min(max_results, 50)},
            units=1,
        )
        return list(data.get("items", []))

    def get_video_details(self, video_ids: list[str]) -> list[dict[str, Any]]:
        """Retrieve full video metadata including duration and tags (1 unit for batch of up to 50)."""
        if not video_ids:
            return []
        joined_ids = ",".join(video_ids[:50])
        data = self._get(
            "videos",
            {"part": "snippet,contentDetails,statistics", "id": joined_ids},
            units=1,
        )
        return list(data.get("items", []))
