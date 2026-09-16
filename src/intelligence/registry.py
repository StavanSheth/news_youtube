"""Compiled Phase 2 runtime registry.

Configuration files remain separate sources of truth; this object is the single
in-memory view consumed by callers that need canonical lookup.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .microtopics import catalog
from .profiles import coverage_report
from .themes import select_theme


class RuntimeRegistry:
    """Canonical in-memory view of layered Phase 2 configuration.

    Precedence is fixed at taxonomy -> matrix -> template -> micro-topic
    override -> theme override.  ``catalog`` performs that merge once; this
    class intentionally only exposes the resolved result.
    """
    def __init__(self, config: Any) -> None:
        self.config = config
        self.entries = catalog(config.taxonomy, config.topics, config.microtopics, config.microtopic_matrix, config.profile_templates)
        self._micro_topics = {entry["micro_topic_id"]: entry for entry in self.entries}
        for entry in self.entries:
            self._micro_topics.setdefault(entry["micro_topic"], entry)
        self._themes = {str(theme.get("id")): theme for theme in config.themes if theme.get("id")}
        self._domains = dict(config.taxonomy.get("domains", {}))
        self._topics = {str(topic.get("key", topic.get("id"))): topic for topic in config.topics}

    def get_micro_topic(self, micro_topic_id: str) -> dict[str, Any]:
        try:
            return self._micro_topics[micro_topic_id]
        except KeyError as error:
            raise KeyError(f"Unknown micro_topic_id: {micro_topic_id}") from error

    def micro_topic(self, micro_topic_id: str) -> dict[str, Any]:
        return self.get_micro_topic(micro_topic_id)

    def get_profile(self, micro_topic_id: str) -> dict[str, Any]:
        return self.get_micro_topic(micro_topic_id)["profile"]

    def classification_profile(self, micro_topic_id: str) -> dict[str, Any]:
        entry = self.get_micro_topic(micro_topic_id)
        return {
            "aliases": entry.get("aliases", []),
            "positive_signals": entry.get("positive_signals", []),
            "negative_signals": entry.get("negative_signals", []),
            "disambiguators": entry.get("disambiguators", []),
            "signal_groups": entry.get("signal_groups", {}),
            "required_signal_groups": entry.get("required_signal_groups", []),
            "group_policy": entry.get("group_policy", {}),
            "primary_threshold": entry.get("primary_threshold"),
            "secondary_threshold": entry.get("secondary_threshold"),
            "max_secondary": entry.get("max_secondary"),
            "runner_up_margin": entry.get("runner_up_margin"),
            "profile_origin": entry.get("profile_origin_code", entry.get("profile_origin")),
        }

    def analysis_profile(self, micro_topic_id: str) -> dict[str, Any]:
        entry = self.get_micro_topic(micro_topic_id)
        return {
            "analysis_contract": entry.get("analysis_contract", {}),
            "retrieval_intent": entry.get("retrieval_intent", {}),
            "profile_quality": entry.get("profile_quality", {}),
        }

    def get_theme(self, theme_id: str) -> dict[str, Any]:
        try:
            return self._themes[theme_id]
        except KeyError as error:
            raise KeyError(f"Unknown theme_id: {theme_id}") from error

    def theme(self, theme_id: str) -> dict[str, Any]:
        return self.get_theme(theme_id)

    def resolve_theme(self, classification: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
        return select_theme(classification, self.config.themes, item)

    def get_domain(self, domain_id: str) -> dict[str, Any]:
        try:
            return self._domains[domain_id]
        except KeyError as error:
            raise KeyError(f"Unknown domain_id: {domain_id}") from error

    def domain(self, domain_id: str) -> dict[str, Any]:
        return self.get_domain(domain_id)

    def get_topic(self, topic_id: str) -> dict[str, Any]:
        try:
            return self._topics[topic_id]
        except KeyError as error:
            raise KeyError(f"Unknown topic_id: {topic_id}") from error

    def topic(self, topic_id: str) -> dict[str, Any]:
        return self.get_topic(topic_id)

    def resolved_microtopics(self, benchmark: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Return deterministic diagnostic records; never use them as input config."""
        readiness = {
            row["micro_topic_id"]: row
            for row in coverage_report(self.entries, self.config.themes, benchmark)["micro_topic_profiles"]
        }
        records = []
        for entry in self.entries:
            theme = select_theme(entry, self.config.themes, {"kind": "news"})
            report = readiness[entry["micro_topic_id"]]
            records.append({
                "micro_topic_id": entry["micro_topic_id"],
                "domain": entry["domain"],
                "parent_topic": entry["topic_key"],
                "name": entry["micro_topic"],
                "enabled": bool(entry.get("enabled", True)),
                "profile_origin": entry.get("profile_origin_code", entry.get("profile_origin")),
                "production_status": "PRODUCTION_READY" if report["production_eligibility"] == "READY" else "UNDER_TEST",
                "source_layers": ["taxonomy", "matrix", "template", *( ["micro_topic_override"] if entry.get("profile_origin_code") == "CURATED" else [])],
                "classification": {
                    "primary_threshold": entry.get("primary_threshold"),
                    "secondary_threshold": entry.get("secondary_threshold"),
                    "group_policy": entry.get("group_policy", {}),
                    "profile_quality": entry.get("profile_quality", {}),
                },
                "theme_resolution": {
                    "theme_id": theme.get("theme_id", theme.get("id")),
                    "resolution_level": theme.get("resolution_level_code"),
                    "theme_origin": theme.get("theme_origin"),
                },
                "analysis_contract": entry.get("analysis_contract", {}),
                "retrieval_intent": entry.get("retrieval_intent", {}),
                "readiness_reasons": report["readiness_reasons"],
            })
        return sorted(records, key=lambda row: row["micro_topic_id"])

    def resolved_themes(self) -> list[dict[str, Any]]:
        return sorted(
            [
                {
                    "theme_id": theme.get("id"), "domain": theme.get("domain"),
                    "micro_topic": theme.get("micro_topic"),
                    "theme_origin": theme.get("theme_origin", "CURATED"),
                    "analysis_contract": theme.get("analysis_contract", {}),
                }
                for theme in self.config.themes
            ],
            key=lambda row: str(row["theme_id"]),
        )

    def diagnostic_manifest(self, benchmark: dict[str, Any] | None = None) -> dict[str, Any]:
        microtopics = self.resolved_microtopics(benchmark)
        themes = self.resolved_themes()
        return {
            "schema": "phase2-resolved-registry/v1",
            "configuration_precedence": ["taxonomy", "matrix", "template", "micro_topic_override", "theme_override"],
            "micro_topic_count": len(microtopics), "theme_count": len(themes),
            "production_ready_count": sum(row["production_status"] == "PRODUCTION_READY" for row in microtopics),
        }

    def write_diagnostics(self, directory: Path, benchmark: dict[str, Any] | None = None) -> None:
        """Write optional, deterministic developer diagnostics outside source config."""
        directory.mkdir(parents=True, exist_ok=True)
        artifacts = {
            "resolved_microtopics.json": self.resolved_microtopics(benchmark),
            "resolved_themes.json": self.resolved_themes(),
            "registry_manifest.json": self.diagnostic_manifest(benchmark),
        }
        for name, value in artifacts.items():
            (directory / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
