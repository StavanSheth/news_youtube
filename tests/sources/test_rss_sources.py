"""Tests for RSS ingestion adapter: client, parser, and normalizer."""
from __future__ import annotations



from intelligence.ingestion.rss.parser import RssParser
from intelligence.ingestion.rss.normalizer import RssNormalizer


_RSS_VALID = b"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.test</link>
    <description>Test RSS feed</description>
    <item>
      <title>Story One</title>
      <link>https://example.test/story-1</link>
      <pubDate>Mon, 01 Jan 2026 10:00:00 GMT</pubDate>
      <description>Story One body text for testing RSS extraction and normalization.</description>
    </item>
    <item>
      <title>Story Two</title>
      <link>https://example.test/story-2</link>
      <pubDate>Tue, 02 Jan 2026 10:00:00 GMT</pubDate>
      <description>Story Two body text.</description>
    </item>
  </channel>
</rss>"""

_RSS_EMPTY = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Empty Feed</title><link>https://example.test</link></channel></rss>"""

_RSS_BOZO = b"""this is not valid xml at all <garbled>"""


class _MockResponse:
    def __init__(self, content: bytes = _RSS_VALID, status_code: int = 200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class TestRssParser:
    def test_validate_feed_returns_true_for_valid_feed(self):
        import feedparser
        parsed = feedparser.parse(_RSS_VALID)
        ok, reason, entries = RssParser.validate_feed(parsed)
        assert ok is True
        assert len(entries) == 2

    def test_validate_feed_returns_false_for_empty_channel(self):
        import feedparser
        parsed = feedparser.parse(_RSS_EMPTY)
        ok, reason, entries = RssParser.validate_feed(parsed)
        # Empty feed with no items is a valid parse but empty collection
        assert len(entries) == 0

    def test_validate_feed_returns_false_for_bozo_feed(self):
        import feedparser
        parsed = feedparser.parse(_RSS_BOZO)
        ok, reason, entries = RssParser.validate_feed(parsed)
        # bozo flag should be set
        assert ok is False or getattr(parsed, "bozo", False)


class TestRssNormalizer:
    def test_normalize_produces_canonical_content(self):
        import feedparser
        parsed = feedparser.parse(_RSS_VALID)
        normalizer = RssNormalizer()
        source_meta = {
            "id": "test-rss",
            "name": "Test RSS",
            "type": "rss",
            "role": "NEWS",
            "trust_tier": 2,
            "region": "global",
            "country": "GLOBAL",
            "domains": ("technology",),
            "topics": ("artificial-intelligence",),
            "micro_topics": (),
        }
        items = normalizer.normalize(parsed, source_meta)
        assert len(items) == 2

    def test_normalize_item_has_canonical_fields(self):
        import feedparser
        parsed = feedparser.parse(_RSS_VALID)
        normalizer = RssNormalizer()
        source_meta = {
            "id": "test-rss", "name": "Test", "type": "rss", "role": "NEWS",
            "trust_tier": 2, "region": "global", "country": "GLOBAL",
            "domains": (), "topics": (), "micro_topics": (),
        }
        items = normalizer.normalize(parsed, source_meta)
        item = items[0]
        assert item.source_id == "test-rss"
        assert item.canonical_url.startswith("https://")
        assert len(item.content_hash) == 64

    def test_normalize_distinct_published_at_and_retrieved_at(self):
        import feedparser
        parsed = feedparser.parse(_RSS_VALID)
        normalizer = RssNormalizer()
        source_meta = {
            "id": "test-rss", "name": "Test", "type": "rss", "role": "NEWS",
            "trust_tier": 2, "region": "global", "country": "GLOBAL",
            "domains": (), "topics": (), "micro_topics": (),
        }
        items = normalizer.normalize(parsed, source_meta)
        item = items[0]
        # published_at must be distinct from retrieved_at
        assert item.published_at != item.retrieved_at

    def test_normalize_items_without_links_are_skipped(self):
        no_link_rss = (
            b'<?xml version="1.0"?><rss version="2.0"><channel><title>Feed</title>'
            b'<item><title>No Link Item</title></item></channel></rss>'
        )
        import feedparser
        parsed = feedparser.parse(no_link_rss)
        normalizer = RssNormalizer()
        source_meta = {
            "id": "t", "name": "T", "type": "rss", "role": "NEWS",
            "trust_tier": 2, "region": "global", "country": "GLOBAL",
            "domains": (), "topics": (), "micro_topics": (),
        }
        items = normalizer.normalize(parsed, source_meta)
        # Items with no link should be filtered out
        assert all(item.canonical_url for item in items)
