from __future__ import annotations

from pathlib import Path
from intelligence.config import load_config

ROOT = Path(__file__).parents[1]


def test_runtime_registry_single_authority():
    config = load_config(ROOT)
    registry = config.registry
    assert registry is not None

    topic = registry.get_micro_topic("foundation-models")
    assert topic["domain"] == "artificial-intelligence"

    profile = registry.classification_profile("foundation-models")
    assert profile["positive_signals"]

    theme = registry.get_theme("ai-agents-intelligence")
    assert theme["domain"] == "artificial-intelligence"
