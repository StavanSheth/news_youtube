"""Live network validation for YouTube Data API (explicit live mode only)."""

from __future__ import annotations

import os
import pytest
from intelligence.ingestion.providers.youtube import YouTubeProvider
from intelligence.sources import SourceContract


def test_youtube_live_network_validation():
    """Verify live YouTube Data API channel retrieval when credentials exist."""
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        pytest.skip("YOUTUBE_API_KEY not configured. Skipping live test.")

    source = SourceContract.from_mapping({
        "id": "deepmind-live",
        "name": "Google DeepMind Live",
        "type": "youtube",
        "role": "VIDEO",
        "trust_tier": 1,
        "url": "https://youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw",
        "authentication_required": True,
        "authentication_env_var": "YOUTUBE_API_KEY",
        "enabled": True,
        "metadata": {"id": "UC_x5XG1OV2P6uZZ5FSM9Ttw"},
    })

    provider = YouTubeProvider()
    result = provider.validate(source, live=True)
    assert result.authenticated
    assert result.status in ("READY", "PASS")
