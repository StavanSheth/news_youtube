"""RSS HTTP client for fetching feed content safely."""

from __future__ import annotations


from ..base import SafeHttpClient


class RssClient:
    """Safe client for retrieving RSS/Atom feeds."""

    def __init__(self, http_client: SafeHttpClient | None = None) -> None:
        self.http_client = http_client or SafeHttpClient(default_timeout=15, max_bytes=5_000_000)

    def fetch_feed(self, url: str, timeout: int | None = None) -> tuple[bytes, int]:
        """Fetch feed XML bytes returning (content, status_code)."""
        response = self.http_client.get(url, timeout=timeout)
        response.raise_for_status()
        return response.content, response.status_code


# Alias for backward compatibility and explicit naming
RssHttpClient = RssClient

