"""Tests for CanonicalContent normalization and SourceItem conversion."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from intelligence.ingestion.base import CanonicalContent
from intelligence.models import SourceItem


NOW_ISO = datetime.now(UTC).isoformat()


def _make_canonical(**overrides) -> CanonicalContent:
    kwargs = dict(
        source_id="test-source",
        source_type="rss",
        source_role="NEWS",
        title="Breaking News Story",
        canonical_url="https://example.com/story-1",
        published_at=NOW_ISO,
        updated_at=NOW_ISO,
        retrieved_at=NOW_ISO,
        author="Staff Writer",
        body_text="A detailed news story with sufficient body content.",
        summary_text="Short summary.",
        evidence_type="article",
        trust_tier=2,
        region="global",
        country="US",
        domains=("technology",),
        topics=("artificial-intelligence",),
        micro_topics=("foundation-models",),
    )
    kwargs.update(overrides)
    return CanonicalContent.create(**kwargs)


class TestCanonicalContent:
    def test_content_id_is_deterministic(self):
        c1 = _make_canonical()
        c2 = _make_canonical()
        assert c1.content_id == c2.content_id

    def test_content_id_differs_for_different_urls(self):
        c1 = _make_canonical(canonical_url="https://example.com/story-1")
        c2 = _make_canonical(canonical_url="https://example.com/story-2")
        assert c1.content_id != c2.content_id

    def test_content_hash_is_sha256(self):
        content = _make_canonical()
        assert len(content.content_hash) == 64
        assert all(c in "0123456789abcdef" for c in content.content_hash)

    def test_content_hash_differs_for_different_bodies(self):
        c1 = _make_canonical(body_text="First story body.")
        c2 = _make_canonical(body_text="Second story body.")
        assert c1.content_hash != c2.content_hash

    def test_title_is_stripped(self):
        content = _make_canonical(title="  Whitespace Story  ")
        assert content.title == "Whitespace Story"

    def test_body_text_is_stripped(self):
        content = _make_canonical(body_text="  body with spaces  ")
        assert content.body_text == "body with spaces"

    def test_to_dict_serializes_tuples_as_lists(self):
        content = _make_canonical()
        d = content.to_dict()
        assert isinstance(d["domains"], list)
        assert isinstance(d["topics"], list)
        assert isinstance(d["micro_topics"], list)

    def test_to_dict_contains_all_canonical_fields(self):
        content = _make_canonical()
        d = content.to_dict()
        required_fields = {
            "content_id", "source_id", "source_type", "source_role",
            "title", "canonical_url", "published_at", "updated_at", "retrieved_at",
            "author", "body_text", "summary_text", "content_hash",
            "evidence_type", "trust_tier", "region", "country",
            "domains", "topics", "micro_topics", "metadata",
        }
        for field in required_fields:
            assert field in d, f"Missing field: {field}"

    def test_to_source_item_conversion(self):
        content = _make_canonical()
        item = content.to_source_item(priority=8.0)
        assert isinstance(item, SourceItem)
        assert item.id == content.content_id
        assert item.title == content.title
        assert item.url == content.canonical_url
        assert item.priority == 8.0

    def test_to_source_item_has_provenance(self):
        content = _make_canonical()
        item = content.to_source_item()
        assert item.provenance is not None
        assert item.provenance.source_id == "test-source"

    def test_to_source_item_metadata_contains_source_fields(self):
        content = _make_canonical()
        item = content.to_source_item()
        meta = item.metadata
        assert "test-source" in meta["source_id"]
        assert meta["source_key"] == "test-source"
        assert meta["source_type"] == "rss"
        assert meta["trust_tier"] == 2

    def test_frozen_dataclass_cannot_be_mutated(self):
        content = _make_canonical()
        with pytest.raises((AttributeError, TypeError)):
            content.title = "new title"  # type: ignore[misc]

    def test_youtube_source_type_maps_to_youtube_kind(self):
        content = _make_canonical(source_type="youtube", evidence_type="transcript")
        item = content.to_source_item()
        assert item.kind == "youtube"

    def test_rss_source_type_maps_to_news_kind(self):
        content = _make_canonical(source_type="rss")
        item = content.to_source_item()
        assert item.kind == "news"
