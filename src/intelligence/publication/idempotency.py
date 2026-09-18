"""Publication idempotency enforcement ensuring zero duplicate runs or emails."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class PublicationIdentity:
    edition_key: str
    publication_id: str
    content_hash: str
    artifact_hash: str

    @classmethod
    def create(
        cls,
        edition_date: str | date,
        edition_type: str,
        timezone: str,
        content_items: list[dict[str, Any]],
        rendered_content: str = "",
    ) -> "PublicationIdentity":
        date_str = edition_date.isoformat() if isinstance(edition_date, date) else str(edition_date)
        edition_key = f"{date_str}|{edition_type.upper()}|{timezone}"

        # Compute stable content hash
        item_keys = sorted(
            f"{item.get('id')}:{item.get('url', '')}:{item.get('published_at', '')}"
            for item in content_items
        )
        content_hash = hashlib.sha256("\n".join(item_keys).encode("utf-8")).hexdigest()[:24]

        # Compute artifact hash
        artifact_hash = hashlib.sha256(rendered_content.encode("utf-8")).hexdigest()[:24] if rendered_content else content_hash

        # Canonical publication ID
        publication_id = hashlib.sha256(f"{edition_key}:{content_hash}".encode("utf-8")).hexdigest()[:24]

        return cls(
            edition_key=edition_key,
            publication_id=publication_id,
            content_hash=content_hash,
            artifact_hash=artifact_hash,
        )


class IdempotencyLedger:
    """Tracks published editions to guarantee idempotent reruns."""

    def __init__(self, existing_records: dict[str, Any] | None = None) -> None:
        self.records = dict(existing_records or {})

    def is_already_published(self, edition_key: str) -> bool:
        record = self.records.get(edition_key)
        return bool(record and record.get("delivery_status") == "DELIVERY_CONFIRMED")

    def record_publication(
        self,
        identity: PublicationIdentity,
        delivery_status: str,
        archive_path: str = "",
    ) -> None:
        self.records[identity.edition_key] = {
            "edition_key": identity.edition_key,
            "publication_id": identity.publication_id,
            "content_hash": identity.content_hash,
            "artifact_hash": identity.artifact_hash,
            "delivery_status": delivery_status,
            "archive_path": archive_path,
        }
