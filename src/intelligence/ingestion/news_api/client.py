"""Generic News API HTTP client with bounded pagination and rate-limit safety."""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

from ..base import SafeHttpClient

LOGGER = logging.getLogger(__name__)


class NewsApiClient:
    """Bounded client for structured News REST APIs."""

    def __init__(
        self,
        api_key_env: str | None = None,
        http_client: SafeHttpClient | None = None,
        default_timeout: int = 15,
        source_id: str = "news_api",
    ) -> None:
        self.api_key_env = api_key_env
        self.http_client = http_client or SafeHttpClient(default_timeout=default_timeout)
        self.source_id = source_id
        self.last_health: dict[str, Any] = {
            "source_id": source_id,
            "status": "INITIALIZED",
            "error_code": None,
            "latency_ms": 0.0,
            "items_count": 0,
        }

    def get_api_key(self) -> str:
        """Resolve API key strictly from environment variable."""
        if not self.api_key_env:
            return ""
        return os.environ.get(self.api_key_env, "").strip()

    def validate_api_key(self) -> bool:
        """Check if required API key is present."""
        if not self.api_key_env:
            return True
        return bool(self.get_api_key())

    def fetch_articles(
        self,
        endpoint_url: str,
        params: dict[str, Any] | None = None,
        auth_header: str | None = "Authorization",
        auth_prefix: str = "Bearer ",
        max_pages: int = 1,
        max_items: int = 50,
    ) -> list[dict[str, Any]]:
        """Fetch articles from REST API with bounded pagination, rate-limit safety, and health telemetry."""
        import time

        start_time = time.perf_counter()
        if self.api_key_env and not self.validate_api_key():
            self.last_health.update({
                "status": "AUTH_FAILED",
                "error_code": f"MISSING_ENV_{self.api_key_env}",
            })
            raise ValueError(f"API key missing from environment variable: {self.api_key_env}")

        api_key = self.get_api_key()
        headers: dict[str, str] = {}
        if api_key and auth_header:
            headers[auth_header] = f"{auth_prefix}{api_key}".strip()

        all_articles: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        seen_urls: set[str] = set()
        current_page = 1
        query_params = dict(params or {})

        try:
            while current_page <= max_pages and len(all_articles) < max_items:
                query_params["page"] = current_page
                response = self.http_client.get(endpoint_url, params=query_params, headers=headers)

                if response.status_code == 429:
                    LOGGER.warning("Rate limit (429) encountered on News API %s", endpoint_url)
                    self.last_health.update({"status": "RATE_LIMITED", "error_code": "HTTP_429"})
                    break

                response.raise_for_status()
                data = response.json() if response.content else {}
                articles = data.get("articles") or data.get("data") or data.get("results") or []

                if not articles:
                    break

                new_in_page = 0
                for art in articles:
                    url = str(art.get("url") or "").strip().lower()
                    aid = str(art.get("id") or url or art.get("title", "")).strip()

                    # Deduplication by ID and URL
                    if (aid and aid in seen_ids) or (url and url in seen_urls):
                        continue

                    # Schema validation: must have title, URL, or ID
                    if not art.get("title") and not url and not art.get("id"):
                        continue

                    seen_ids.add(aid)
                    if url:
                        seen_urls.add(url)

                    all_articles.append(art)
                    new_in_page += 1
                    if len(all_articles) >= max_items:
                        break

                if new_in_page == 0:
                    break

                current_page += 1

            if self.last_health.get("status") not in ("RATE_LIMITED", "AUTH_FAILED"):
                latency = round((time.perf_counter() - start_time) * 1000.0, 2)
                self.last_health.update({
                    "status": "READY" if all_articles else "EMPTY",
                    "error_code": None,
                    "latency_ms": latency,
                    "items_count": len(all_articles),
                })
            return all_articles

        except Exception as exc:
            latency = round((time.perf_counter() - start_time) * 1000.0, 2)
            err_code = type(exc).__name__
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                err_code = f"HTTP_{exc.response.status_code}"
            self.last_health.update({
                "status": "ERROR",
                "error_code": err_code,
                "latency_ms": latency,
                "items_count": len(all_articles),
            })
            return []
