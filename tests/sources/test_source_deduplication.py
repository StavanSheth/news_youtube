"""Tests for content deduplication using canonical URL + content hash."""
from __future__ import annotations

from datetime import UTC, datetime


from intelligence.ingestion.base import CanonicalContent


NOW_ISO = datetime.now(UTC).isoformat()


def _make_canonical(url: str, body: str, title: str = "Story", **overrides) -> CanonicalContent:
    kwargs = dict(
        source_id="test-source",
        source_type="rss",
        source_role="NEWS",
        title=title,
        canonical_url=url,
        published_at=NOW_ISO,
        updated_at=NOW_ISO,
        retrieved_at=NOW_ISO,
        author="Author",
        body_text=body,
        summary_text="Summary",
        evidence_type="article",
        trust_tier=2,
        region="global",
        country="GLOBAL",
        domains=("technology",),
        topics=("artificial-intelligence",),
        micro_topics=(),
    )
    kwargs.update(overrides)
    return CanonicalContent.create(**kwargs)


class TestDeduplication:
    def test_same_url_same_body_yields_same_content_id(self):
        c1 = _make_canonical("https://example.com/story-1", "Same body text.")
        c2 = _make_canonical("https://example.com/story-1", "Same body text.")
        assert c1.content_id == c2.content_id

    def test_different_url_yields_different_content_id(self):
        c1 = _make_canonical("https://example.com/story-1", "Same body text.")
        c2 = _make_canonical("https://example.com/story-2", "Same body text.")
        assert c1.content_id != c2.content_id

    def test_same_url_different_body_stable_content_id_different_hash(self):
        c1 = _make_canonical("https://example.com/story-1", "First body.")
        c2 = _make_canonical("https://example.com/story-1", "Second body.")
        # Canonical URL provides stable content_id across article revisions
        assert c1.content_id == c2.content_id
        assert c1.content_hash != c2.content_hash

    def test_urlless_items_differ_by_body_or_title(self):
        c1 = _make_canonical("", "First body.")
        c2 = _make_canonical("", "Second body.")
        assert c1.content_id != c2.content_id

        c3 = _make_canonical("", "Same body.", title="Title A")
        c4 = _make_canonical("", "Same body.", title="Title B")
        assert c3.content_id != c4.content_id

    def test_dedup_set_using_content_id(self):
        items = [
            _make_canonical("https://example.com/s1", "Body 1"),
            _make_canonical("https://example.com/s1", "Body 1"),  # duplicate
            _make_canonical("https://example.com/s2", "Body 2"),
        ]
        seen: set[str] = set()
        unique = []
        for item in items:
            if item.content_id not in seen:
                seen.add(item.content_id)
                unique.append(item)
        assert len(unique) == 2

    def test_dedup_set_using_content_hash(self):
        items = [
            _make_canonical("https://example.com/s", "Same body."),
            _make_canonical("https://example.com/s", "Same body."),  # duplicate
        ]
        seen_hashes: set[str] = set()
        unique = [i for i in items if not (i.content_hash in seen_hashes or seen_hashes.add(i.content_hash))]  # type: ignore
        assert len(unique) == 1

    def test_whitespace_normalization_does_not_break_dedup(self):
        c1 = _make_canonical("https://example.com/s", "  Body  ")
        c2 = _make_canonical("https://example.com/s", "Body")
        # Body text is stripped so these should match
        assert c1.content_hash == c2.content_hash
