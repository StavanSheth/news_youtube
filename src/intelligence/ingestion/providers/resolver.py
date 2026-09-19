"""Authoritative ProviderResolver dispatching source contracts to typed provider adapters."""

from __future__ import annotations

from typing import Any

from ...sources import SourceContract
from .base import SourceProvider
from .news_api import NewsAPIProvider
from .rss import RSSProvider
from .source_item import SourceItem
from .youtube import YouTubeProvider


class GenericHTTPProvider:
    """Fallback provider for generic HTTP source contracts."""

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = timeout_seconds

    def validate(self, source: SourceContract | dict[str, Any], live: bool = False) -> tuple[bool, list[str]]:
        url = getattr(source, "url", None) or source.get("url")
        if not url:
            return False, ["MISSING_SOURCE_URL"]
        return True, []

    def collect(self, source: SourceContract | dict[str, Any], limit: int = 10) -> list[Any]:
        return []

    def health(self, source: SourceContract | dict[str, Any]) -> dict[str, Any]:
        return {"status": "CONFIGURED", "reachable": True}


class ProviderResolver:
    """Resolves and dispatches ingestion operations to concrete provider adapters."""

    def __init__(
        self,
        rss_provider: RSSProvider | None = None,
        news_api_provider: NewsAPIProvider | None = None,
        youtube_provider: YouTubeProvider | None = None,
        generic_http_provider: GenericHTTPProvider | None = None,
    ) -> None:
        self.rss_provider = rss_provider or RSSProvider()
        self.news_api_provider = news_api_provider or NewsAPIProvider()
        self.youtube_provider = youtube_provider or YouTubeProvider()
        self.generic_http_provider = generic_http_provider or GenericHTTPProvider()

    def resolve(self, source: SourceContract | dict[str, Any]) -> SourceProvider:
        """Resolve the appropriate SourceProvider adapter for a source contract."""
        stype = (getattr(source, "type", None) or source.get("type", "")).lower()
        method = (getattr(source, "collection_method", None) or source.get("collection_method", "")).lower()

        if stype == "rss" or method == "rss" or "feed" in stype:
            return self.rss_provider
        if stype in ("news_api", "newsapi") or method in ("news_api", "newsapi"):
            return self.news_api_provider
        if stype == "youtube" or method == "youtube":
            return self.youtube_provider
        return self.generic_http_provider

    def collect_source_items(
        self,
        source: SourceContract | dict[str, Any],
        limit: int = 10,
    ) -> list[SourceItem]:
        """Collect and normalize items into canonical SourceItem representations."""
        provider = self.resolve(source)
        stype = (getattr(source, "type", None) or source.get("type", "")).lower()

        raw_canonical = provider.collect(source, limit=limit)
        items: list[SourceItem] = []

        sid = getattr(source, "id", None) or source.get("id", "unknown")
        lic = getattr(source, "license_status", None) or source.get("license", "standard_license")
        ret = getattr(source, "retention_policy", None) or source.get("retention_policy", "standard_retention")

        for c in raw_canonical:
            if isinstance(c, SourceItem):
                items.append(c)
            elif hasattr(c, "canonical_url"):
                # CanonicalContent instance
                items.append(
                    SourceItem.from_canonical_content(
                        content=c,
                        provider=stype,
                        source_id=sid,
                        license=lic,
                        retention_policy=ret,
                    )
                )

        return items
