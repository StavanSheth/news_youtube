"""News API normalizer mapping generic REST payloads to canonical content."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..base import CanonicalContent


class NewsApiNormalizer:
    """Normalizes generic News API JSON payloads into CanonicalContent records."""

    @classmethod
    def normalize_article(
        cls,
        article: dict[str, Any],
        source: Any,
        retrieved_at: datetime | None = None,
    ) -> CanonicalContent | None:
        """Convert a JSON article record into a CanonicalContent record."""
        url = str(article.get("url") or article.get("canonical_url", "")).strip()
        title = str(article.get("title", "")).strip()
        if not url or not title:
            return None

        published_at = str(article.get("publishedAt") or article.get("published_at") or "").strip()
        updated_at = str(article.get("updatedAt") or article.get("updated_at", "")).strip()
        retrieved_iso = (retrieved_at or datetime.now(UTC)).isoformat()

        author = str(article.get("author", "")).strip()
        content = str(article.get("content") or article.get("body") or article.get("text", "")).strip()
        description = str(article.get("description") or article.get("summary", "")).strip()
        body_text = content or description or title

        if isinstance(source, dict):
            source_id = source.get("id") or source.get("source_id") or "news_api"
            source_type = source.get("type", "api")
            role_obj = source.get("role", "NEWS")
            trust_tier = int(source.get("trust_tier", 2))
            region = source.get("region", "global")
            country = source.get("country", "GLOBAL")
            domains = tuple(source.get("domains", ()))
            topics = tuple(source.get("topics", ()))
            micro_topics = tuple(source.get("micro_topics", ()))
        else:
            source_id = getattr(source, "id", getattr(source, "source_id", "news_api"))
            source_type = getattr(source, "type", "api")
            role_obj = getattr(source, "role", "NEWS")
            trust_tier = int(getattr(source, "trust_tier", 2))
            region = getattr(source, "region", "global")
            country = getattr(source, "country", "GLOBAL")
            domains = tuple(getattr(source, "domains", ()))
            topics = tuple(getattr(source, "topics", ()))
            micro_topics = tuple(getattr(source, "micro_topics", ()))
        source_role = role_obj.value if hasattr(role_obj, "value") else str(role_obj)

        return CanonicalContent.create(
            source_id=source_id,
            source_type=source_type,
            source_role=source_role,
            title=title,
            canonical_url=url,
            published_at=published_at,
            updated_at=updated_at,
            retrieved_at=retrieved_iso,
            author=author,
            body_text=body_text,
            summary_text=description,
            evidence_type="article",
            trust_tier=trust_tier,
            region=region,
            country=country,
            domains=domains,
            topics=topics,
            micro_topics=micro_topics,
            metadata=dict(article.get("metadata", {})),
        )
