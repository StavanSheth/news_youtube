"""Authoritative newsletter package providing report models and independent renderers."""

from __future__ import annotations

from .html import render_html
from .markdown import render_markdown
from .model import NewsletterModel

__all__ = [
    "NewsletterModel",
    "render_html",
    "render_markdown",
]
