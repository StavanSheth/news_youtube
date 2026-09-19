"""RSS feed parser wrapping feedparser with robust error detection."""

from __future__ import annotations

import logging
from typing import Any

import feedparser

LOGGER = logging.getLogger(__name__)


class RssParser:
    """Parser for RSS and Atom feeds."""

    @classmethod
    def parse_content(cls, content: bytes | str) -> feedparser.FeedParserDict:
        """Parse raw content bytes into FeedParserDict."""
        parsed = feedparser.parse(content)
        return parsed

    @classmethod
    def validate_feed(cls, parsed: feedparser.FeedParserDict) -> tuple[bool, str, list[dict[str, Any]]]:
        """Validate parsed feed structure, bozo flags, and non-empty entries."""
        entries = list(getattr(parsed, "entries", []) or [])
        bozo = getattr(parsed, "bozo", False)
        bozo_exc = getattr(parsed, "bozo_exception", None)

        if bozo and not entries:
            err_msg = type(bozo_exc).__name__ if bozo_exc else "INVALID_FEED_SYNTAX"
            return False, f"BOZO_ERROR: {err_msg}", []

        if not entries:
            return True, "EMPTY_FEED", []

        return True, "VALID", entries
