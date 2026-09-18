"""Deterministic theme routing and observable fallback tracking."""

from __future__ import annotations

from typing import Any
from .contracts import ThemeResolution
from .quality import theme_quality_score, theme_specificity_score


class ThemeResolutionRecord(str):
    """String-compatible mapping record for theme resolution traces."""

    def __new__(cls, code: str, data: dict[str, Any]) -> "ThemeResolutionRecord":
        instance = super().__new__(cls, code)
        instance._data = data
        return instance

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, str):
            return self._data[key]
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)

    def __contains__(self, item: Any) -> bool:
        if isinstance(item, str) and item in self._data:
            return True
        return super().__contains__(item)


def _resolution(
    theme: dict[str, Any],
    level: str,
    *,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    origin = str(theme.get("theme_origin", "CURATED" if level == "EXACT_MICRO_TOPIC" else "FALLBACK"))
    resolved_level_map = {
        "EXACT_MICRO_TOPIC": "micro_topic",
        "TOPIC_FALLBACK": "topic",
        "DOMAIN_FALLBACK": "domain",
        "CONTROLLED_FALLBACK": "controlled_fallback",
        "GLOBAL_FALLBACK": "global_fallback",
    }
    resolved_level = resolved_level_map.get(level, level.lower())
    fallback_used = level != "EXACT_MICRO_TOPIC"

    res = ThemeResolution(
        requested_level="micro_topic",
        resolved_level=resolved_level,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        theme_id=str(theme.get("id", "")),
        specificity_score=theme_specificity_score(theme),
        theme_origin=origin,
        quality_score=theme_quality_score(theme),
    )
    resolution_record = ThemeResolutionRecord(level, res.to_dict())

    return {
        **theme,
        **res.to_metadata(),
        "theme_resolution": resolution_record,
        "theme_resolution_record": res.to_dict(),
        "resolution_level": {"EXACT_MICRO_TOPIC": "exact_micro_topic", "TOPIC_FALLBACK": "topic_fallback", "DOMAIN_FALLBACK": "domain_family", "GLOBAL_FALLBACK": "global_fallback", "CONTROLLED_FALLBACK": "controlled_fallback"}.get(level, level.lower()),
        "theme_origin": origin,
    }


def select_theme(
    classification: dict[str, Any],
    themes: list[dict[str, Any]],
    item: dict[str, Any],
) -> dict[str, Any]:
    """Resolve exact micro-topic, topic, domain, then global themes in strict order."""
    stream = "video" if item.get("kind") == "youtube" else "news"
    candidates: list[tuple[int, dict[str, Any]]] = []

    for theme in themes:
        if theme.get("id") == "domain-fallback":
            continue
        if theme.get("domain", "all") not in {"all", classification.get("domain")}:
            continue
        streams = theme.get("content_stream", ["all"])
        if isinstance(streams, str):
            streams = [streams]
        if "all" not in streams and stream not in streams:
            continue
        micro = theme.get("micro_topic", "any")
        topic = theme.get("topic", "any")
        if micro not in {"any", classification.get("micro_topic")}:
            continue
        if topic not in {"any", classification.get("topic"), classification.get("topic_key")}:
            continue

        if micro == classification.get("micro_topic"):
            level = 4
        elif topic not in {"any", None}:
            level = 3
        elif theme.get("domain", "all") == classification.get("domain"):
            level = 2
        else:
            level = 1

        level_code = {
            4: "EXACT_MICRO_TOPIC",
            3: "TOPIC_FALLBACK",
            2: "DOMAIN_FALLBACK",
            1: "GLOBAL_FALLBACK",
        }[level]
        fallback_reason = None if level == 4 else (
            "exact_micro_topic_theme_missing" if level == 3
            else "exact_and_topic_theme_missing" if level == 2
            else "exact_topic_domain_theme_missing"
        )
        candidates.append((level, _resolution(theme, level_code, fallback_reason=fallback_reason)))

    if candidates:
        best_level = max(level for level, _ in candidates)
        best = [theme for level, theme in candidates if level == best_level]
        if len(best) > 1:
            best.sort(key=lambda theme: (-int(theme.get("priority", 0)), str(theme.get("id", ""))))
        selected = best[0]
        if stream == "video" and "main_argument" not in selected.get("questions", []):
            selected = {
                **selected,
                "questions": [*selected.get("questions", []), "main_argument", "claims", "methods", "limitations"],
            }
        selected = {
            **selected,
            "theme_id": selected.get("id"),
            "theme_specificity_score": theme_specificity_score(selected),
            "fallback_reason": None if not selected.get("fallback_used") else selected.get("fallback_reason", "exact_theme_missing"),
        }
        return selected

    # Controlled configured fallback: explicit and observable; no theme is silently invented.
    fallback = next((theme for theme in themes if theme.get("id") == "domain-fallback"), {})
    if not fallback:
        raise ValueError(f"No configured theme or controlled fallback for {classification.get('micro_topic')}")

    res = ThemeResolution(
        requested_level="micro_topic",
        resolved_level="controlled_fallback",
        fallback_used=True,
        fallback_reason="no_exact_topic_or_domain_theme",
        theme_id=str(fallback.get("id", "domain-fallback")),
        specificity_score=theme_specificity_score(fallback),
        theme_origin=str(fallback.get("theme_origin", "FALLBACK")),
        quality_score=theme_quality_score(fallback),
    )
    resolution_record = ThemeResolutionRecord("CONTROLLED_FALLBACK", res.to_dict())

    return {
        **fallback,
        "domain": classification.get("domain", ""),
        "topic": classification.get("topic", ""),
        "micro_topic": classification.get("micro_topic", ""),
        "content_stream": [stream],
        "questions": fallback.get("content_streams", {}).get(stream, {}).get("questions", fallback.get("questions", [])),
        "resolution_level": "controlled_fallback",
        "fallback_used": True,
        "theme_id": fallback.get("id", "domain-fallback"),
        "theme_origin": fallback.get("theme_origin", "FALLBACK"),
        "fallback_reason": "no_exact_topic_or_domain_theme",
        "theme_specificity_score": theme_specificity_score(fallback),
        "theme_quality_score": theme_quality_score(fallback),
        "resolution_level_code": "CONTROLLED_FALLBACK",
        "theme_resolution": resolution_record,
        "theme_resolution_record": res.to_dict(),
    }
