"""Tests for YouTube ingestion: quota tracking, transcript handling, client, and normalizer."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from intelligence.ingestion.youtube.quota import YouTubeQuotaTracker
from intelligence.ingestion.youtube.transcripts import (
    TranscriptStatus,
    YouTubeTranscriptHandler,
)
from intelligence.ingestion.youtube.client import YouTubeClient
from intelligence.ingestion.youtube.normalizer import YouTubeNormalizer
from intelligence.ingestion.base import CanonicalContent


class TestYouTubeQuotaTracker:
    def test_initial_state(self):
        tracker = YouTubeQuotaTracker(max_units_per_run=100)
        assert tracker.can_spend(1)
        assert tracker.youtube_units == 0
        assert tracker.youtube_requests == 0
        assert not tracker.quota_exceeded

    def test_record_success_increments_units_and_requests(self):
        tracker = YouTubeQuotaTracker(max_units_per_run=100)
        tracker.record_success(units=5)
        assert tracker.youtube_requests == 1
        assert tracker.youtube_units == 5
        assert tracker.youtube_last_success is not None

    def test_cannot_spend_when_units_exceed_max(self):
        tracker = YouTubeQuotaTracker(max_units_per_run=10)
        tracker.record_success(units=9)
        assert tracker.can_spend(1)
        assert not tracker.can_spend(2)

    def test_quota_exceeded_flag_blocks_all_requests(self):
        tracker = YouTubeQuotaTracker(max_units_per_run=1000)
        tracker.record_failure(is_quota_exceeded=True)
        assert tracker.quota_exceeded
        assert not tracker.can_spend(1)

    def test_rate_limit_failure_increments_rate_limit_events(self):
        tracker = YouTubeQuotaTracker()
        tracker.record_failure(is_rate_limit=True)
        assert tracker.youtube_rate_limit_events == 1
        assert tracker.youtube_failures == 1
        assert tracker.youtube_last_failure is not None

    def test_to_dict_serializes_state(self):
        tracker = YouTubeQuotaTracker(max_units_per_run=50)
        tracker.record_success(units=2)
        d = tracker.to_dict()
        assert d["max_units_per_run"] == 50
        assert d["youtube_units"] == 2
        assert d["youtube_requests"] == 1


class TestYouTubeTranscripts:
    def test_not_requested_returns_not_requested_status(self):
        text, meta = YouTubeTranscriptHandler.fetch_transcript("test_vid", requested=False)
        assert text == ""
        assert meta["transcript_status"] == TranscriptStatus.NOT_REQUESTED.value

    def test_successful_transcript_extraction(self):
        mock_api_instance = MagicMock()
        mock_fetched = MagicMock()
        mock_fetched.to_raw_data.return_value = [
            {"text": "Hello world", "start": 0.0, "duration": 2.0},
            {"text": "welcome to the show", "start": 2.0, "duration": 3.0},
        ]
        mock_fetched.language_code = "en"
        mock_api_instance.fetch.return_value = mock_fetched

        with patch("intelligence.ingestion.youtube.transcripts.YouTubeTranscriptApi", return_value=mock_api_instance):
            text, meta = YouTubeTranscriptHandler.fetch_transcript("vid123", requested=True)
            assert text == "Hello world welcome to the show"
            assert meta["transcript_status"] == TranscriptStatus.AVAILABLE.value
            assert meta["transcript_language"] == "en"
            assert "transcript_retrieved_at" in meta

    def test_empty_transcript_handling(self):
        mock_api_instance = MagicMock()
        mock_fetched = MagicMock()
        mock_fetched.to_raw_data.return_value = []
        mock_fetched.language_code = "en"
        mock_api_instance.fetch.return_value = mock_fetched

        with patch("intelligence.ingestion.youtube.transcripts.YouTubeTranscriptApi", return_value=mock_api_instance):
            text, meta = YouTubeTranscriptHandler.fetch_transcript("vid123", requested=True)
            assert text == ""
            assert meta["transcript_status"] == TranscriptStatus.EMPTY.value

    def test_disabled_transcript_classified_as_unavailable(self):
        class TranscriptsDisabled(Exception):
            pass

        mock_api_instance = MagicMock()
        mock_api_instance.fetch.side_effect = TranscriptsDisabled("Subtitles are disabled for this video")

        with patch("intelligence.ingestion.youtube.transcripts.YouTubeTranscriptApi", return_value=mock_api_instance):
            text, meta = YouTubeTranscriptHandler.fetch_transcript("vid123", requested=True)
            assert text == ""
            assert meta["transcript_status"] == TranscriptStatus.UNAVAILABLE.value

    def test_private_video_classified_as_not_allowed(self):
        class PrivateVideoError(Exception):
            pass

        mock_api_instance = MagicMock()
        mock_api_instance.fetch.side_effect = PrivateVideoError("Permission denied: video is private")

        with patch("intelligence.ingestion.youtube.transcripts.YouTubeTranscriptApi", return_value=mock_api_instance):
            text, meta = YouTubeTranscriptHandler.fetch_transcript("vid123", requested=True)
            assert text == ""
            assert meta["transcript_status"] == TranscriptStatus.NOT_ALLOWED.value


class TestYouTubeClient:
    def test_missing_api_key_raises(self):
        client = YouTubeClient(api_key="")
        with pytest.raises(ValueError, match="YouTube API key is missing"):
            client.get_channel_uploads_playlist("UC123")

    def test_quota_exceeded_raises_runtime_error(self):
        tracker = YouTubeQuotaTracker(max_units_per_run=10)
        tracker.record_success(units=10)
        client = YouTubeClient(api_key="test_key", quota_tracker=tracker)
        with pytest.raises(RuntimeError, match="quota limit exceeded"):
            client.get_channel_uploads_playlist("UC123")

    def test_get_channel_uploads_playlist_success(self):
        mock_http = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU123"}}}]}'
        mock_response.json.return_value = {
            "items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU123"}}}]
        }
        mock_http.get.return_value = mock_response

        tracker = YouTubeQuotaTracker(max_units_per_run=50)
        client = YouTubeClient(api_key="test_key", quota_tracker=tracker, http_client=mock_http)
        uploads_id = client.get_channel_uploads_playlist("UC123")
        assert uploads_id == "UU123"
        assert tracker.youtube_units == 1

    def test_get_playlist_items_success(self):
        mock_http = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"items": [{"id": "item1"}]}'
        mock_response.json.return_value = {"items": [{"id": "item1"}]}
        mock_http.get.return_value = mock_response

        tracker = YouTubeQuotaTracker(max_units_per_run=50)
        client = YouTubeClient(api_key="test_key", quota_tracker=tracker, http_client=mock_http)
        items = client.get_playlist_items("UU123", max_results=10)
        assert len(items) == 1
        assert tracker.youtube_units == 1

    def test_get_video_details_empty_list_returns_empty_without_call(self):
        mock_http = MagicMock()
        tracker = YouTubeQuotaTracker(max_units_per_run=50)
        client = YouTubeClient(api_key="test_key", quota_tracker=tracker, http_client=mock_http)
        details = client.get_video_details([])
        assert details == []
        assert not mock_http.get.called


class TestYouTubeNormalizer:
    def test_normalize_video_returns_canonical_content(self):
        snippet = {
            "title": "State of AI 2026",
            "description": "An overview of new models.",
            "publishedAt": "2026-09-01T12:00:00Z",
            "channelId": "UC_AI_LAB",
            "channelTitle": "AI Lab",
            "tags": ["ai", "deep learning"],
        }
        content_details = {"duration": "PT45M"}
        source = {
            "id": "youtube-ai-lab",
            "role": "VIDEO",
            "trust_tier": 1,
            "region": "global",
            "country": "US",
        }
        canonical = YouTubeNormalizer.normalize_video(
            video_id="xyz789",
            snippet=snippet,
            content_details=content_details,
            transcript_text="Welcome to this comprehensive overview.",
            transcript_metadata={"transcript_status": "TRANSCRIPT_AVAILABLE"},
            source=source,
        )
        assert isinstance(canonical, CanonicalContent)
        assert canonical.source_id == "youtube-ai-lab"
        assert canonical.canonical_url == "https://www.youtube.com/watch?v=xyz789"
        assert canonical.evidence_type == "transcript"
        assert "Welcome to this comprehensive overview" in canonical.body_text
        assert canonical.metadata["video_id"] == "xyz789"
        assert canonical.metadata["duration"] == "PT45M"

    def test_podcast_classification_from_title(self):
        snippet = {
            "title": "AI Breakthroughs Episode 42 Interview with Founder",
            "description": "Detailed discussion.",
            "publishedAt": "2026-09-01T12:00:00Z",
            "channelId": "UC1",
            "channelTitle": "Tech Pod",
        }
        canonical = YouTubeNormalizer.normalize_video(video_id="v1", snippet=snippet)
        assert canonical.metadata["content_type"] == "podcast"

    def test_video_without_transcript_sets_evidence_type_to_video(self):
        snippet = {
            "title": "Short Clip",
            "description": "Short summary",
            "publishedAt": "2026-09-01T12:00:00Z",
            "channelId": "UC1",
            "channelTitle": "Tech Pod",
        }
        canonical = YouTubeNormalizer.normalize_video(video_id="v2", snippet=snippet, transcript_text="")
        assert canonical.evidence_type == "video"
