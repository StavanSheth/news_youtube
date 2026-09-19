"""Item-level processor decoupling normalization, classification, and theme routing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ..contracts import EvidenceType, provenance_from_mapping, source_timestamps_from_mapping
from ..identity import make_content_id, make_source_id
from ..microtopics import classify_micro_topics


@dataclass(frozen=True)
class SourceItem:
    """Standardized input envelope for collected items."""

    id: str
    source: str
    kind: str = "article"
    title: str = ""
    url: str = ""
    text: str = ""
    published_at: str = ""
    priority: int = 5
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "kind": self.kind,
            "title": self.title,
            "url": self.url,
            "text": self.text,
            "published_at": self.published_at,
            "priority": self.priority,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceItem":
        return cls(
            id=str(data.get("id", "")),
            source=str(data.get("source", "unknown")),
            kind=str(data.get("kind", "article")),
            title=str(data.get("title", "")),
            url=str(data.get("url", "")),
            text=str(data.get("text", "")),
            published_at=str(data.get("published_at", "")),
            priority=int(data.get("priority", 5)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class ProcessedItem:
    """Decoupled result of item-level normalization, classification, and routing."""

    item_id: str
    source_id: str
    content_id: str
    classification: dict[str, Any] = field(default_factory=dict)
    theme: dict[str, Any] = field(default_factory=dict)
    micro_topic_jobs: list[dict[str, Any]] = field(default_factory=list)
    timestamps: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    status: str = "PROCESSED"
    normalized_item: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "source_id": self.source_id,
            "content_id": self.content_id,
            "classification": dict(self.classification),
            "theme": dict(self.theme),
            "micro_topic_jobs": list(self.micro_topic_jobs),
            "timestamps": dict(self.timestamps),
            "provenance": dict(self.provenance),
            "status": self.status,
            "normalized_item": dict(self.normalized_item),
        }


class ItemProcessor:
    """Authoritative item processor performing normalization, classification, and job envelope preparation."""

    def __init__(
        self,
        themes: list[dict[str, Any]] | None = None,
        micro_topic_catalog: list[dict[str, Any]] | None = None,
        settings: dict[str, Any] | None = None,
    ) -> None:
        if themes is None:
            from ..infrastructure.config import load_application_config
            cfg = load_application_config()
            self.themes = list(cfg.themes)
        else:
            self.themes = list(themes)

        if micro_topic_catalog is None:
            from ..microtopics import catalog
            self.catalog = catalog()
        else:
            self.catalog = list(micro_topic_catalog)

        self.settings = dict(settings or {})

    def resolve_theme(self, classification: dict[str, Any]) -> dict[str, Any]:
        """Resolve theme from configured themes matching micro-topic, domain, or default."""
        target_micro = str(classification.get("micro_topic_id") or classification.get("micro_topic", "")).lower()
        target_domain = str(classification.get("domain", "")).lower()

        # 1. Exact micro-topic match
        for theme in self.themes:
            theme_micro = str(theme.get("micro_topic", theme.get("micro_topic_id", ""))).lower()
            if theme_micro and theme_micro == target_micro:
                return theme

        # 2. Domain match
        for theme in self.themes:
            theme_domain = str(theme.get("domain", "")).lower()
            if theme_domain and theme_domain == target_domain:
                return theme

        # 3. First available or fallback
        if self.themes:
            return self.themes[0]

        return {
            "id": f"theme-{target_domain or 'general'}",
            "domain": target_domain or "general",
            "micro_topic": target_micro or "general",
            "questions": ["what_changed", "why_it_matters"],
        }

    def process_item(self, item: SourceItem | dict[str, Any]) -> ProcessedItem:
        """Process a source item: normalize, classify, route theme, and produce micro-topic jobs."""
        raw_dict = item.to_dict() if isinstance(item, SourceItem) else dict(item)
        metadata = dict(raw_dict.get("metadata", {}))

        # 1. Identity
        source_name = raw_dict.get("source", "unknown")
        source_id = str(metadata.get("source_id") or make_source_id(source_name))
        url = str(raw_dict.get("url", ""))
        title = str(raw_dict.get("title", ""))
        published_at = str(raw_dict.get("published_at", ""))
        text = str(raw_dict.get("text", "")).strip()

        content_id = str(
            metadata.get("content_id")
            or make_content_id(source_id, url, title, published_at, text)
        )

        # 2. Timestamps
        ts_contract = source_timestamps_from_mapping(raw_dict)
        timestamps_dict = ts_contract.to_dict()

        # 3. Provenance
        provenance_dict: dict[str, Any] = {}
        if url.startswith(("http://", "https://")):
            provenance_type = EvidenceType.TRANSCRIPT if raw_dict.get("kind") == "youtube" else EvidenceType.ARTICLE
            prov = provenance_from_mapping(
                {
                    **raw_dict,
                    "metadata": {
                        **metadata,
                        "source_id": source_id,
                        "content_id": content_id,
                        "retrieved_at": timestamps_dict.get("retrieved_at") or datetime.now(UTC).isoformat(),
                    },
                },
                provenance_type,
                text[:200] if text else title,
            )
            provenance_dict = prov.to_dict()

        # 4. Classification
        classifications: list[dict[str, Any]] = []
        if metadata.get("classification"):
            classifications.append(metadata["classification"])
        elif metadata.get("classifications"):
            classifications.extend(metadata["classifications"])
        else:
            item_payload = {"title": title, "text": text, "url": url}
            classified = classify_micro_topics(item_payload, self.catalog)
            classifications = classified or []

        primary_classification = classifications[0] if classifications else {
            "domain": "general",
            "topic": "general",
            "micro_topic": "general",
            "micro_topic_id": "general",
            "signals": [],
        }

        # 5. Theme routing
        theme = self.resolve_theme(primary_classification) if classifications else {}

        # 6. Build micro-topic jobs
        jobs: list[dict[str, Any]] = []
        for cls_info in classifications:
            micro_id = str(cls_info.get("micro_topic_id") or cls_info.get("micro_topic", ""))
            jobs.append({
                "micro_topic_id": micro_id,
                "content_id": content_id,
                "source_id": source_id,
                "classification": cls_info,
                "theme": self.resolve_theme(cls_info),
                "priority": raw_dict.get("priority", 5),
            })

        micro_topic_id = str(primary_classification.get("micro_topic_id") or primary_classification.get("micro_topic", "")) if classifications else ""
        normalized_item = {
            **raw_dict,
            "text": text,
            "metadata": {
                **metadata,
                "source_id": source_id,
                "content_id": content_id,
                "micro_topic_id": micro_topic_id,
                "classification": primary_classification if classifications else {},
                "classifications": classifications,
                "provenance": provenance_dict,
            },
        }

        return ProcessedItem(
            item_id=str(raw_dict.get("id", content_id)),
            source_id=source_id,
            content_id=content_id,
            classification=primary_classification,
            theme=theme,
            micro_topic_jobs=jobs,
            timestamps=timestamps_dict,
            provenance=provenance_dict,
            status="PROCESSED",
            normalized_item=normalized_item,
        )
