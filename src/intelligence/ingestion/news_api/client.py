"""Generic News API HTTP client with bounded pagination and rate-limit safety."""

from __future__ import annotations

import logging
import os
from typing import Any

from ..base import SafeHttpClient

LOGGER = logging.getLogger(__name__)


class NewsApiClient:
    """Bounded client for structured News REST APIs."""

    def __init__(
        self,
        api_key_env: str | None = None,
        http_client: SafeHttpClient | None = None,
        default_timeout: int = 15,
    ) -> None:
        self.api_key_env = api_key_env
        self.http_client = http_client or SafeHttpClient(default_timeout=default_timeout)

    def get_api_key(self) -> str:
        """Resolve API key strictly from environment variable."""
        if not self.api_key_env:
            return ""
        return os.environ.get(self.api_key_env, "").strip()

    def fetch_articles(
        self,
        endpoint_url: str,
        params: dict[str, Any] | None = None,
        auth_header: str | None = "Authorization",
        auth_prefix: str = "Bearer ",
        max_pages: int = 1,
        max_items: int = 50,
    ) -> list[dict[str, Any]]:
        """Fetch articles from REST API with bounded pagination and rate-limit detection."""
        api_key = self.get_api_key()
        headers: dict[str, str] = {}
        if api_key and auth_header:
            headers[auth_header] = f"{auth_prefix}{api_key}".strip()

        all_articles: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        current_page = 1
        query_params = dict(params or {})

        while current_page <= max_pages and len(all_articles) < max_items:
            query_params["page"] = current_page
            response = self.http_client.get(endpoint_url, params=query_params, headers=headers)
            
            if response.status_code == 429:
                LOGGER.warning("Rate limit encountered on News API %s", endpoint_url)
                break

            response.raise_for_status()
            data = response.json() if response.content else {}
            articles = data.get("articles") or data.get("data") or data.get("results") or []
            
            if not articles:
                break

            new_in_page = 0
            for art in articles:
                aid = str(art.get("id") or art.get("url") or art.get("title", ""))
                if aid and aid not in seen_ids:
                    seen_ids.add(aid)
                    all_articles.append(art)
                    new_in_page += 1
                    if len(all_articles) >= max_items:
                        break

            if new_in_page == 0:
                break  # Stop if no new items found on this page

            current_page += 1

        return all_articles
