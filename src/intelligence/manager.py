from __future__ import annotations

from typing import Any, Protocol
from .evidence_scope import EvidenceScope
from .evidence_projection import project_micro_topic_context
from .identity import make_content_id, make_source_id

from .retrieval import RAGManager
from .themes import analysis_profile, select_theme
from .statuses import IntelligenceStatus


class RAGProvider(Protocol):
    metrics: dict[str, Any]

    def retrieve(
        self,
        item: dict[str, Any],
        classification: dict[str, Any],
        theme: dict[str, Any],
        event_context: dict[str, Any] | None = None,
        scope: EvidenceScope | None = None,
    ) -> dict[str, Any]: ...


class MicroTopicManager:
    """AI-last orchestrator: one bounded request per relevant micro-topic."""

    def __init__(self, provider: Any, themes: list[dict[str, Any]], settings: dict[str, Any], retriever: RAGProvider | None = None) -> None:
        self.provider, self.themes, self.settings = provider, themes, settings
        self.rag = retriever or RAGManager(settings)
        self.stats = {"micro_topic_analyses": 0, "retrieval_calls": 0, "ai_calls": 0, "retries": 0, "retrieval": self.rag.metrics}

    def analyze(self, item: dict[str, Any], classifications: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results = []
        seen: set[tuple[str, str]] = set()
        for classification in classifications:
            key = (classification.get("domain", ""), classification.get("micro_topic", ""))
            if key in seen:
                continue
            seen.add(key)
            theme = select_theme(classification, self.themes, item)
            profile = analysis_profile(classification, theme, item)
            evidence_item, scope = self._isolate_item(item, classification)
            self.stats["retrieval_calls"] += 1
            packet = self.rag.retrieve(evidence_item, classification, theme, evidence_item.get("metadata", {}).get("event_context"), scope)
            evidence = packet["chunks"]
            if not evidence:
                results.append({
                    "classification": classification, "theme": theme, "profile": profile,
                    "evidence": [], "retrieval": packet, "analysis": {},
                    "analysis_status": packet.get("status", "EMPTY_RETRIEVAL"),
                })
                continue
            max_context = int(self.settings.get("max_retrieved_context_chars", 12000))
            bounded = []
            used = 0
            for entry in evidence:
                if used >= max_context:
                    break
                bounded.append({**entry, "text": entry["text"][: max_context - used]})
                used += len(bounded[-1]["text"])
            self.stats["micro_topic_analyses"] += 1
            try:
                analysis = self._analyze_with_retry(project_micro_topic_context(evidence_item, classification, scope, bounded), profile, bounded)
                analysis_status = "OK"
            except (TimeoutError, ValueError, RuntimeError) as error:
                analysis = {}
                analysis_status = IntelligenceStatus.ANALYSIS_FAILURE.value
                self.stats.setdefault("analysis_failures", 0)
                self.stats["analysis_failures"] += 1
            results.append({
                "classification": classification, "theme": theme, "profile": profile, "evidence": bounded,
                "retrieval": {**packet, "chunks": bounded},
                "analysis": analysis,
                "analysis_status": analysis_status,
            })
        return results

    @staticmethod
    def _isolate_item(item: dict[str, Any], classification: dict[str, Any]) -> tuple[dict[str, Any], EvidenceScope]:
        """Attach a micro-topic scope without deleting context from the source item.

        Retrieval enforces the scope on canonical chunks. Keeping the original
        document here preserves cross-sentence context for claims and entities.
        """
        source_name = str(item.get("source", "")).strip()
        source_id = str(item.get("metadata", {}).get("source_id", "")).strip()
        if not source_id:
            if not source_name:
                raise ValueError("Evidence scope requires a source identity")
            source_id = make_source_id(source_name)
        content_id = str(item.get("metadata", {}).get("content_id", "")).strip()
        if not content_id:
            content_id = make_content_id(source_id, item.get("url", ""), item.get("title", ""), item.get("published_at", ""), item.get("text", ""))
        scope = EvidenceScope(
            micro_topic_id=str(classification.get("micro_topic_id", classification.get("micro_topic", ""))),
            source_content_id=content_id,
            source_id=source_id,
            allowed_events=tuple(filter(None, [item.get("metadata", {}).get("event_id", "")])),
            isolation_confidence=float(classification.get("classification_confidence", classification.get("confidence", 0.0))),
        )
        metadata = {**item.get("metadata", {}), "classification": classification, **scope.to_metadata()}
        return {**item, "metadata": metadata}, scope

    def _analyze_with_retry(self, item: dict[str, Any], profile: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
        attempts = max(1, int(self.settings.get("max_ai_attempts", 2)))
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                self.stats["ai_calls"] += 1
                return self.provider.analyze_micro_topic(item, profile, evidence)
            except (ValueError, TypeError, KeyError, TimeoutError) as error:
                last_error = error
                if attempt + 1 < attempts:
                    self.stats["retries"] += 1
        raise last_error or RuntimeError("AI analysis failed")


IntelligenceManager = MicroTopicManager
