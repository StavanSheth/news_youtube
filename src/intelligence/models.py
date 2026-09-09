from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SourceItem:
    id: str
    kind: str
    title: str
    url: str
    text: str
    published_at: str = ""
    source: str = ""
    priority: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Analysis:
    item: SourceItem
    topics: list[str]
    score: float
    facts: list[str]
    interpretation: list[str]
    actionable_insights: list[str]
    routine: dict[str, list[str]] | None = None
    uncertainties: list[str] = field(default_factory=list)
    processed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["item"] = self.item.to_dict()
        return payload
