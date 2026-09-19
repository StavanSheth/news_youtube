"""YouTube transcript extraction and state machine."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from youtube_transcript_api import YouTubeTranscriptApi


class TranscriptStatus(StrEnum):
    AVAILABLE = "TRANSCRIPT_AVAILABLE"
    UNAVAILABLE = "TRANSCRIPT_UNAVAILABLE"
    FAILED = "TRANSCRIPT_FAILED"
    EMPTY = "TRANSCRIPT_EMPTY"
    NOT_ALLOWED = "TRANSCRIPT_NOT_ALLOWED"
    NOT_REQUESTED = "NOT_REQUESTED"


class YouTubeTranscriptHandler:
    """Handles fetching and explicit state reporting for YouTube transcripts."""

    @classmethod
    def fetch_transcript(
        cls,
        video_id: str,
        languages: list[str] | None = None,
        requested: bool = True,
    ) -> tuple[str, dict[str, Any]]:
        """Fetch transcript text and structured status metadata."""
        if not requested:
            return "", {"transcript_status": TranscriptStatus.NOT_REQUESTED.value}

        try:
            api = YouTubeTranscriptApi()
            fetched = api.fetch(video_id, languages=languages or ["en"])
            rows = fetched.to_raw_data()
            text = " ".join(str(row.get("text", "")) for row in rows).strip()

            if not text:
                return "", {
                    "transcript_status": TranscriptStatus.EMPTY.value,
                    "transcript_language": getattr(fetched, "language_code", ""),
                }

            return text, {
                "transcript_status": TranscriptStatus.AVAILABLE.value,
                "transcript_language": getattr(fetched, "language_code", ""),
                "transcript_retrieved_at": datetime.now(UTC).isoformat(),
            }

        except Exception as error:
            name = type(error).__name__.lower()
            msg = str(error).lower()
            
            if any(token in name or token in msg for token in ("disabled", "notranscript", "notranscripts", "nosubtitles")):
                status = TranscriptStatus.UNAVAILABLE.value
            elif any(token in name or token in msg for token in ("permission", "notallowed", "forbidden", "private", "age")):
                status = TranscriptStatus.NOT_ALLOWED.value
            else:
                status = TranscriptStatus.FAILED.value

            return "", {
                "transcript_status": status,
                "transcript_reason": type(error).__name__,
            }
