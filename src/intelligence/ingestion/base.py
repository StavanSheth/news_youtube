"""Base contracts, canonical content envelopes, and safe network client for ingestion."""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Protocol

import requests

from ..contracts import EvidenceType, Provenance, SourceTimestamps
from ..identity import make_content_id, make_evidence_id
from ..models import SourceItem
from ..observability.logging import mask_secrets

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CanonicalContent:
    """Canonical normalized content item entering the intelligence pipeline and RAG."""

    content_id: str
    source_id: str
    source_type: str
    source_role: str
    title: str
    canonical_url: str
    published_at: str
    updated_at: str
    retrieved_at: str
    author: str
    body_text: str
    summary_text: str
    content_hash: str
    evidence_type: str
    trust_tier: int = 2
    region: str = "global"
    country: str = "GLOBAL"
    domains: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    micro_topics: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        source_id: str,
        source_type: str,
        source_role: str,
        title: str,
        canonical_url: str,
        published_at: str,
        updated_at: str,
        retrieved_at: str,
        author: str,
        body_text: str,
        summary_text: str,
        evidence_type: str,
        trust_tier: int = 2,
        region: str = "global",
        country: str = "GLOBAL",
        domains: tuple[str, ...] = (),
        topics: tuple[str, ...] = (),
        micro_topics: tuple[str, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> CanonicalContent:
        clean_url = canonical_url.strip()
        clean_title = title.strip()
        text_for_hash = body_text.strip() or summary_text.strip() or clean_title
        hash_input = f"{clean_url}|{clean_title}|{text_for_hash}".encode("utf-8")
        content_hash = hashlib.sha256(hash_input).hexdigest()
        content_id = make_content_id(source_id, clean_url, clean_title, published_at, text_for_hash)

        return cls(
            content_id=content_id,
            source_id=source_id,
            source_type=source_type,
            source_role=source_role,
            title=clean_title,
            canonical_url=clean_url,
            published_at=published_at,
            updated_at=updated_at,
            retrieved_at=retrieved_at,
            author=author.strip(),
            body_text=body_text.strip(),
            summary_text=summary_text.strip(),
            content_hash=content_hash,
            evidence_type=evidence_type,
            trust_tier=trust_tier,
            region=region,
            country=country,
            domains=domains,
            topics=topics,
            micro_topics=micro_topics,
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["domains"] = list(self.domains)
        result["topics"] = list(self.topics)
        result["micro_topics"] = list(self.micro_topics)
        return result

    def to_source_item(self, priority: float = 1.0) -> SourceItem:
        """Convert canonical content to pipeline SourceItem with full provenance."""
        ev_type = (
            EvidenceType.TRANSCRIPT
            if self.evidence_type == "transcript"
            else EvidenceType.ARTICLE
        )
        text_content = self.body_text or self.summary_text or self.title
        meta = {
            **self.metadata,
            "content_id": self.content_id,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "source_role": self.source_role,
            "trust_tier": self.trust_tier,
            "region": self.region,
            "country": self.country,
            "domains": list(self.domains),
            "topics": list(self.topics),
            "micro_topics": list(self.micro_topics),
            "content_hash": self.content_hash,
            "author": self.author,
            "summary": self.summary_text,
            "updated_at": self.updated_at,
            "retrieved_at": self.retrieved_at,
        }
        timestamps = SourceTimestamps.from_values(
            published_at=self.published_at,
            updated_at=self.updated_at,
            retrieved_at=self.retrieved_at,
        )
        prov = Provenance(
            evidence_id=make_evidence_id(self.content_id, ev_type.value, text_content[:360], self.canonical_url),
            content_id=self.content_id,
            source_id=self.source_id,
            source_url=self.canonical_url,
            evidence_type=ev_type,
            trust_tier=self.trust_tier,
            retrieved_at=datetime.fromisoformat(self.retrieved_at.replace("Z", "+00:00")),
        )
        return SourceItem(
            id=self.content_id,
            kind="youtube" if self.source_type == "youtube" else "news",
            title=self.title,
            url=self.canonical_url,
            text=text_content,
            published_at=self.published_at,
            source=self.source_id,
            priority=priority,
            metadata=meta,
            timestamps=timestamps,
            provenance=prov,
        )


class SafeHttpClient:
    """Safe bounded HTTP client enforcing timeouts, size limits, and bounded retries."""

    NON_RETRYABLE_STATUSES = {400, 401, 403, 404, 405, 410, 422}
    RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}

    def __init__(
        self,
        default_timeout: int = 15,
        max_bytes: int = 5_000_000,
        max_retries: int = 2,
        user_agent: str = "news-youtube-intelligence/1.0",
    ) -> None:
        self.default_timeout = default_timeout
        self.max_bytes = max_bytes
        self.max_retries = max_retries
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

    def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
    ) -> requests.Response:
        """Execute GET with bounded retries and response size check."""
        t_out = timeout or self.default_timeout
        retries = self.max_retries if max_retries is None else max_retries
        req_headers = dict(headers or {})
        
        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=req_headers,
                    timeout=t_out,
                    stream=True,
                )
                
                # Check for non-retryable 4xx
                if response.status_code in self.NON_RETRYABLE_STATUSES:
                    LOGGER.debug("Non-retryable status %d for %s", response.status_code, mask_secrets(url))
                    return response

                # Check for retryable status
                if response.status_code in self.RETRYABLE_STATUSES and attempt < retries:
                    LOGGER.warning("Retryable status %d (attempt %d/%d) for %s", response.status_code, attempt + 1, retries, mask_secrets(url))
                    time.sleep(0.5 * (2 ** attempt))
                    continue

                # Bounded response size check
                content_chunks: list[bytes] = []
                total_bytes = 0
                for chunk in response.iter_content(chunk_size=65536):
                    total_bytes += len(chunk)
                    if total_bytes > self.max_bytes:
                        LOGGER.warning("Response exceeded max_bytes (%d > %d) for %s", total_bytes, self.max_bytes, mask_secrets(url))
                        break
                    content_chunks.append(chunk)

                # Set full content on response
                response._content = b"".join(content_chunks)
                return response

            except (requests.Timeout, requests.ConnectionError) as exc:
                last_exc = exc
                LOGGER.warning("Transient network error (attempt %d/%d): %s", attempt + 1, retries, type(exc).__name__)
                if attempt < retries:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
            except requests.RequestException as exc:
                LOGGER.warning("Non-retryable request error: %s", type(exc).__name__)
                raise

        if last_exc:
            raise last_exc
        raise RuntimeError(f"Request failed after {retries} retries")


class BaseProviderAdapter(Protocol):
    """Protocol for provider ingestion adapters."""

    def collect(self, source: Mapping[str, Any]) -> list[CanonicalContent]:
        """Collect and normalize items from the source."""
        ...
