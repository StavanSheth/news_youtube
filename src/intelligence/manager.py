from __future__ import annotations

from typing import Any, Protocol
from .evidence_scope import EvidenceScope, EvidenceScopeBuilder
from .evidence_projection import project_micro_topic_context

from .retrieval import RAGManager
from .themes import analysis_profile, select_theme
from .statuses import IntelligenceStatus
from .contracts import ContextBudget, MicroTopicDecision, MicroTopicJob


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

    def __init__(self, provider: Any, themes: Any, settings: dict[str, Any], retriever: RAGProvider | None = None) -> None:
        self.provider = provider
        if hasattr(themes, "get_theme") or hasattr(themes, "config"):
            self.registry = themes
            self.themes = themes.config.themes
        else:
            self.registry = None
            self.themes = themes
        self.settings = settings
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
                    "evidence_state": packet.get("status", IntelligenceStatus.INSUFFICIENT_EVIDENCE.value),
                    "analysis_eligible": False,
                })
                continue
            budget = ContextBudget(max_context_chars=int(self.settings.get("max_retrieved_context_chars", 12000)))
            max_context = budget.analysis_chars
            bounded = []
            used = 0
            for entry in evidence:
                entry_size = len(entry.get("text", ""))
                if used + entry_size > max_context:
                    continue
                bounded.append(entry)
                used += entry_size
            self.stats["micro_topic_analyses"] += 1
            job = MicroTopicJob(
                micro_topic_id=str(classification.get("micro_topic_id", classification.get("micro_topic", ""))),
                domain_id=str(classification.get("domain", "")), topic_id=str(classification.get("topic_id", classification.get("topic_key", ""))),
                decision=MicroTopicDecision.from_mapping(classification.get("decision_contract", {"micro_topic_id": classification.get("micro_topic", ""), "domain_id": classification.get("domain", ""), "topic_id": classification.get("topic_key", ""), "decision": classification.get("decision", "PRIMARY"), "score": classification.get("classification_score", 0), "confidence": classification.get("confidence", 0), "threshold": classification.get("threshold", 0), "margin": classification.get("margin", 0), "matched_signals": classification.get("signals", []), "profile_origin": classification.get("profile_origin_code")})),
                theme=theme, evidence_scope=scope.to_metadata(), retrieval_intent=profile.get("retrieval_intent", {}), analysis_requirements=profile.get("analysis_contract", {}), confidence=float(classification.get("confidence", 0)), provenance={"content_id": scope.source_content_id, "source_id": scope.source_id},
            )
            try:
                analysis = self._analyze_with_retry(project_micro_topic_context(evidence_item, classification, scope, bounded), {**profile, "micro_topic_job": job.to_dict()}, bounded)
                analysis_status = "OK"
                evidence_state = IntelligenceStatus.ANALYSIS_COMPLETED.value
            except (TimeoutError, ValueError, RuntimeError):
                analysis = {}
                analysis_status = IntelligenceStatus.ANALYSIS_FAILURE.value
                evidence_state = IntelligenceStatus.ANALYSIS_FAILURE.value
                self.stats.setdefault("analysis_failures", 0)
                self.stats["analysis_failures"] += 1
            results.append({
                "classification": classification, "theme": theme, "profile": profile, "evidence": bounded,
                "retrieval": {**packet, "chunks": bounded},
                "analysis": analysis,
                "analysis_status": analysis_status,
                "evidence_state": evidence_state,
                "analysis_eligible": True,
            })
        return results

    @staticmethod
    def _isolate_item(item: dict[str, Any], classification: dict[str, Any]) -> tuple[dict[str, Any], EvidenceScope]:
        """Attach a micro-topic scope without deleting context from the source item.

        Retrieval enforces the scope on canonical chunks. Keeping the original
        document here preserves cross-sentence context for claims and entities.
        """
        if not str(item.get("source", "")).strip() and not str(item.get("metadata", {}).get("source_id", "")).strip():
            raise ValueError("Evidence scope requires a source identity")
        scope = EvidenceScopeBuilder.build(item, classification)
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
