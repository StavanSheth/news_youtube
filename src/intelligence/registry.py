"""Compiled Phase 2 runtime registry.

Configuration files remain separate sources of truth; this object is the single
in-memory view consumed by callers that need canonical lookup.
"""

from __future__ import annotations

from typing import Any

from .microtopics import catalog


class RuntimeRegistry:
    def __init__(self, config: Any) -> None:
        self.config = config
        self.entries = catalog(config.taxonomy, config.topics, config.microtopics, config.microtopic_matrix, config.profile_templates)
        self._micro_topics = {entry["micro_topic_id"]: entry for entry in self.entries}
        self._themes = {str(theme.get("id")): theme for theme in config.themes if theme.get("id")}
        self._domains = dict(config.taxonomy.get("domains", {}))
        self._topics = {str(topic.get("key", topic.get("id"))): topic for topic in config.topics}

    def get_micro_topic(self, micro_topic_id: str) -> dict[str, Any]:
        try:
            return self._micro_topics[micro_topic_id]
        except KeyError as error:
            raise KeyError(f"Unknown micro_topic_id: {micro_topic_id}") from error

    def get_profile(self, micro_topic_id: str) -> dict[str, Any]:
        return self.get_micro_topic(micro_topic_id)["profile"]

    def get_theme(self, theme_id: str) -> dict[str, Any]:
        try:
            return self._themes[theme_id]
        except KeyError as error:
            raise KeyError(f"Unknown theme_id: {theme_id}") from error

    def get_domain(self, domain_id: str) -> dict[str, Any]:
        try:
            return self._domains[domain_id]
        except KeyError as error:
            raise KeyError(f"Unknown domain_id: {domain_id}") from error

    def get_topic(self, topic_id: str) -> dict[str, Any]:
        try:
            return self._topics[topic_id]
        except KeyError as error:
            raise KeyError(f"Unknown topic_id: {topic_id}") from error
