"""Authoritative normalized SourceItem model for unified provider ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..base import CanonicalContent


@dataclass
class SourceItem:
    """Unified provider source item preserving origin metadata, license, and provenance."""

    source_id: str
    provider: str
    external_id: str
    url: str
    title: str
    description: str
    published_at: str
    retrieved_at: str
    author: str = "Unknown"
    content: str = ""
    content_type: str = "text/plain"
    language: str = "en"
    region: str = "global"
    topics: list[str] = field(default_factory=list)
    micro_topics: list[str] = field(default_factory=list)
    license: str = "all_rights_reserved"
    retention_policy: str = "standard_retention"
    provenance: dict[str, Any] = field(default_factory=dict)
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    def to_canonical_content(self) -> CanonicalContent:
        """Convert SourceItem to CanonicalContent for RAG chunking and indexing."""
        return CanonicalContent.create(
            source_id=self.source_id,
            source_type=self.provider.lower(),
            source_role="NEWS",
            title=self.title,
            canonical_url=self.url,
            published_at=self.published_at,
            updated_at=self.published_at,
            retrieved_at=self.retrieved_at,
            author=self.author,
            body_text=self.content or self.description,
            summary_text=self.description,
            evidence_type="article" if self.provider.lower() != "youtube" else "video",
            region=self.region,
            topics=tuple(self.topics),
            micro_topics=tuple(self.micro_topics),
            trust_tier=self.provenance.get("trust_tier", 2),
            metadata={
                "license": self.license,
                "retention_policy": self.retention_policy,
                **self.raw_metadata,
            },
        )

    @classmethod
    def from_canonical_content(
        cls,
        content: CanonicalContent,
        provider: str = "rss",
        source_id: str = "",
        license: str = "standard_license",
        retention_policy: str = "standard_retention",
    ) -> SourceItem:
        """Construct a SourceItem from existing CanonicalContent."""
        return cls(
            source_id=content.source_id or source_id,
            provider=provider,
            external_id=content.content_id,
            url=content.canonical_url,
            title=content.title,
            description=content.summary_text,
            published_at=content.published_at,
            retrieved_at=content.retrieved_at,
            author=content.author,
            content=content.body_text,
            content_type="text/plain",
            language="en",
            region=content.region,
            topics=list(content.topics),
            micro_topics=list(content.micro_topics),
            license=license,
            retention_policy=retention_policy,
            provenance={
                "source_id": content.source_id,
                "content_id": content.content_id,
                "trust_tier": content.trust_tier,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "provider": self.provider,
            "external_id": self.external_id,
            "url": self.url,
            "title": self.title,
            "description": self.description,
            "published_at": self.published_at,
            "retrieved_at": self.retrieved_at,
            "author": self.author,
            "content": self.content,
            "content_type": self.content_type,
            "language": self.language,
            "region": self.region,
            "topics": self.topics,
            "micro_topics": self.micro_topics,
            "license": self.license,
            "retention_policy": self.retention_policy,
            "provenance": self.provenance,
        }
