from __future__ import annotations

from pathlib import Path
from intelligence.config import load_config
from intelligence.themes import theme_quality_score, theme_specificity_score, theme_fingerprint

ROOT = Path(__file__).parents[1]


def test_theme_quality_and_differentiation():
    config = load_config(ROOT)
    themes = config.themes

    exact_themes = [t for t in themes if t.get("micro_topic") not in {None, "any", "*"}]
    assert len(exact_themes) >= 200

    for theme in exact_themes:
        quality = theme_quality_score(theme)
        specificity = theme_specificity_score(theme)
        assert quality > 0.0
        assert specificity > 0.0

    foundation = next(t for t in exact_themes if t.get("micro_topic") == "foundation-models")
    agents = next(t for t in exact_themes if t.get("micro_topic") == "ai-agents")
    assert theme_fingerprint(foundation) != theme_fingerprint(agents)
