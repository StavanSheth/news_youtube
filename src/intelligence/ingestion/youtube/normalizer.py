"""YouTube normalizer converting video metadata and transcripts into canonical content."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..base import CanonicalContent


class YouTubeNormalizer:
    """Normalizes YouTube videos into canonical content records."""

    @classmethod
    def normalize_video(
        cls,
        video_id: str,
        snippet: dict[str, Any],
        content_details: dict[str, Any] | None = None,
        transcript_text: str = "",
        transcript_metadata: dict[str, Any] | None = None,
        source: Any = None,
        retrieved_at: datetime | None = None,
    ) -> CanonicalContent:
        """Convert a YouTube video record into a CanonicalContent item."""
        title = str(snippet.get("title", "Untitled video")).strip()
        description = str(snippet.get("description", "")).strip()
        published_at = str(snippet.get("publishedAt", "")).strip()
        retrieved_iso = (retrieved_at or datetime.now(UTC)).isoformat()
        canonical_url = f"https://www.youtube.com/watch?v={video_id}"

        content_parts = [title]
        if description:
            content_parts.append(description)
        if transcript_text:
            content_parts.append(transcript_text)
        body_text = "\n\n".join(content_parts)

        # Content classification
        title_lower = title.lower()
        is_podcast = any(token in title_lower for token in ("podcast", "interview", "conversation", "episode", "discussion"))
        content_type = "podcast" if is_podcast else "video"

        # Source attributes
        if isinstance(source, dict):
            source_id = source.get("id") or source.get("source_id") or snippet.get("channelId", "youtube")
            source_type = "youtube"
            role_obj = source.get("role", "VIDEO")
            trust_tier = int(source.get("trust_tier", 2))
            region = source.get("region", "global")
            country = source.get("country", "GLOBAL")
            domains = tuple(source.get("domains", ("artificial-intelligence",)))
            topics = tuple(source.get("topics", ("foundation-models",)))
            micro_topics = tuple(source.get("micro_topics", ()))
        else:
            source_id = getattr(source, "id", getattr(source, "source_id", snippet.get("channelId", "youtube")))
            source_type = "youtube"
            role_obj = getattr(source, "role", "VIDEO")
            trust_tier = int(getattr(source, "trust_tier", 2))
            region = getattr(source, "region", "global")
            country = getattr(source, "country", "GLOBAL")
            domains = tuple(getattr(source, "domains", ("artificial-intelligence",)))
            topics = tuple(getattr(source, "topics", ("foundation-models",)))
            micro_topics = tuple(getattr(source, "micro_topics", ()))
        source_role = role_obj.value if hasattr(role_obj, "value") else str(role_obj)

        tags = list(snippet.get("tags", []))
        duration = (content_details or {}).get("duration", "")

        meta = {
            "video_id": video_id,
            "channel_id": snippet.get("channelId", ""),
            "channel_title": snippet.get("channelTitle", ""),
            "duration": duration,
            "tags": tags,
            "content_type": content_type,
            **(transcript_metadata or {}),
        }

        return CanonicalContent.create(
            source_id=source_id,
            source_type=source_type,
            source_role=source_role,
            title=title,
            canonical_url=canonical_url,
            published_at=published_at,
            updated_at=published_at,
            retrieved_at=retrieved_iso,
            author=snippet.get("channelTitle", ""),
            body_text=body_text,
            summary_text=description[:1000] if description else title,
            evidence_type="transcript" if transcript_text else "video",
            trust_tier=trust_tier,
            region=region,
            country=country,
            domains=domains,
            topics=topics,
            micro_topics=micro_topics,
            metadata=meta,
        )
