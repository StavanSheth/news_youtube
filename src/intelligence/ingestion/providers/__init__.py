"""Provider-specific source ingestion and validation package."""

from __future__ import annotations

from .base import SourceProvider
from .news_api import NewsAPIProvider
from .resolver import GenericHTTPProvider, ProviderResolver
from .rss import RSSProvider
from .source_item import SourceItem
from .youtube import YouTubeProvider

__all__ = [
    "SourceProvider",
    "RSSProvider",
    "NewsAPIProvider",
    "YouTubeProvider",
    "GenericHTTPProvider",
    "ProviderResolver",
    "SourceItem",
]
