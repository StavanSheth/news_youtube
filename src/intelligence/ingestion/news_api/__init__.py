"""News API ingestion sub-package."""
from .client import NewsApiClient
from .normalizer import NewsApiNormalizer

__all__ = ["NewsApiClient", "NewsApiNormalizer"]
