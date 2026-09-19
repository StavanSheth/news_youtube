"""Tests for News API ingestion: client, pagination, rate-limit safety, and normalizer."""
from __future__ import annotations

from unittest.mock import MagicMock

from intelligence.ingestion.news_api.client import NewsApiClient
from intelligence.ingestion.news_api.normalizer import NewsApiNormalizer
from intelligence.ingestion.base import CanonicalContent


class TestNewsApiClient:
    def test_get_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("TEST_NEWS_KEY", "secret-token-123")
        client = NewsApiClient(api_key_env="TEST_NEWS_KEY")
        assert client.get_api_key() == "secret-token-123"

    def test_get_api_key_missing_env(self, monkeypatch):
        monkeypatch.delenv("NONEXISTENT_KEY", raising=False)
        client = NewsApiClient(api_key_env="NONEXISTENT_KEY")
        assert client.get_api_key() == ""

    def test_fetch_articles_bounded_pagination(self):
        mock_http = MagicMock()

        # Page 1 response
        resp1 = MagicMock()
        resp1.status_code = 200
        resp1.content = b'{"articles": [{"id": "1", "title": "Article 1"}]}'
        resp1.json.return_value = {"articles": [{"id": "1", "title": "Article 1"}]}

        # Page 2 response
        resp2 = MagicMock()
        resp2.status_code = 200
        resp2.content = b'{"articles": [{"id": "2", "title": "Article 2"}]}'
        resp2.json.return_value = {"articles": [{"id": "2", "title": "Article 2"}]}

        mock_http.get.side_effect = [resp1, resp2]

        client = NewsApiClient(http_client=mock_http)
        articles = client.fetch_articles(
            "https://api.example.com/v2/news",
            max_pages=2,
            max_items=10,
        )

        assert len(articles) == 2
        assert articles[0]["id"] == "1"
        assert articles[1]["id"] == "2"
        assert mock_http.get.call_count == 2

    def test_fetch_articles_respects_max_items(self):
        mock_http = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b'{"articles": [{"id": "1"}, {"id": "2"}, {"id": "3"}]}'
        resp.json.return_value = {
            "articles": [{"id": "1"}, {"id": "2"}, {"id": "3"}]
        }
        mock_http.get.return_value = resp

        client = NewsApiClient(http_client=mock_http)
        articles = client.fetch_articles(
            "https://api.example.com/v2/news",
            max_pages=5,
            max_items=2,
        )

        assert len(articles) == 2

    def test_fetch_articles_handles_429_gracefully(self):
        mock_http = MagicMock()
        resp = MagicMock()
        resp.status_code = 429
        mock_http.get.return_value = resp

        client = NewsApiClient(http_client=mock_http)
        articles = client.fetch_articles("https://api.example.com/v2/news", max_pages=3)
        assert articles == []

    def test_fetch_articles_deduplicates_by_id(self):
        mock_http = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b'{"articles": [{"id": "1", "title": "A"}, {"id": "1", "title": "A duplicate"}]}'
        resp.json.return_value = {
            "articles": [{"id": "1", "title": "A"}, {"id": "1", "title": "A duplicate"}]
        }
        mock_http.get.return_value = resp

        client = NewsApiClient(http_client=mock_http)
        articles = client.fetch_articles("https://api.example.com/v2/news", max_pages=1)
        assert len(articles) == 1


class TestNewsApiNormalizer:
    def test_normalize_valid_article(self):
        article = {
            "url": "https://example.com/ai-report-2026",
            "title": "New Foundation Model Released",
            "publishedAt": "2026-09-15T08:30:00Z",
            "author": "Jane Doe",
            "description": "A breakthrough in reasoning benchmarks.",
            "content": "Full article body about the breakthrough...",
            "metadata": {"category": "tech"},
        }
        source = {
            "id": "test-news-api",
            "role": "NEWS",
            "trust_tier": 1,
            "region": "global",
            "country": "US",
            "domains": ("technology",),
            "topics": ("artificial-intelligence",),
        }
        canonical = NewsApiNormalizer.normalize_article(article, source)
        assert isinstance(canonical, CanonicalContent)
        assert canonical.source_id == "test-news-api"
        assert canonical.title == "New Foundation Model Released"
        assert canonical.canonical_url == "https://example.com/ai-report-2026"
        assert canonical.author == "Jane Doe"
        assert canonical.trust_tier == 1
        assert canonical.evidence_type == "article"
        assert "Full article body" in canonical.body_text

    def test_normalize_missing_url_returns_none(self):
        article = {"title": "No URL"}
        assert NewsApiNormalizer.normalize_article(article, {}) is None

    def test_normalize_missing_title_returns_none(self):
        article = {"url": "https://example.com/notitle"}
        assert NewsApiNormalizer.normalize_article(article, {}) is None
