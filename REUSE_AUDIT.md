# REUSE AUDIT: SET E PHASE 2

## 1. Component Audit Summary

| Metric | Value |
| :--- | :--- |
| **Total relevant functions/classes audited** | 42 |
| **Reusable unchanged** | 24 |
| **Reusable after refactor** | 12 |
| **Duplicated (consolidated into canonical)** | 4 |
| **Deprecated / Wrapped** | 2 |
| **Deleted** | 0 |
| **Newly introduced** | 6 |

### Reuse Ratio Calculation
$$\text{reuse\_ratio} = \frac{\text{existing reused or refactored components}}{\text{total relevant components}} = \frac{24 + 12}{42} = \frac{36}{42} = 85.7\%$$

---

## 2. Component-by-Component Classification

### A. Reusable Unchanged (24 components)
- `KeywordClassifier` (`src/intelligence/classification.py`)
- `group_policy_satisfied`, `phrase_found` (`src/intelligence/microtopics/signals.py`)
- `MicroTopicDecision` (`src/intelligence/microtopics/decisions.py`)
- `compute_confidence` (`src/intelligence/microtopics/scoring.py`)
- `classify_micro_topics` (`src/intelligence/microtopics/classifier.py`)
- `EvidenceScope` (`src/intelligence/evidence_scope.py`)
- `score_micro_topic_chunk` (`src/intelligence/microtopics/__init__.py`)
- `build_retrieval_request`, `RetrievalRequest` (`src/intelligence/rag/query.py`)
- `BM25L`, `compute_dense_vector`, `cosine_similarity` (`src/intelligence/rag/index.py`)
- `apply_diversity_filtering` (`src/intelligence/rag/diversity.py`)
- `ContextBudgeter`, `BudgetTrace` (`src/intelligence/rag/budget.py`)
- `ContextPacket` (`src/intelligence/rag/packet.py`)
- `validate_analysis_schema` (`src/intelligence/validation/schema.py`)
- `validate_semantic_content` (`src/intelligence/validation/semantic.py`)
- `validate_usefulness` (`src/intelligence/validation/usefulness.py`)
- `validate_claim_provenance`, `verify_provenance` (`src/intelligence/validation/provenance.py`)
- `validate_business_rules` (`src/intelligence/validation/business.py`)
- `BudgetManager`, `BudgetLimits`, `BudgetUsage`, `BudgetSkipRecord` (`src/intelligence/budgets/manager.py`)
- `TokenUsage`, `calculate_cost`, `estimate_tokens` (`src/intelligence/ai/usage.py`)
- `with_retry` (`src/intelligence/ai/retry.py`)
- `classify_gemini_error`, `ProviderError` (`src/intelligence/ai/errors.py`)
- `NewsletterModel`, `render_markdown`, `render_html` (`src/intelligence/newsletter/`)
- `PersistencePaths` (`src/intelligence/persistence/__init__.py`)
- `source_timestamps_from_mapping`, `make_content_id`, `make_source_id` (`src/intelligence/contracts.py`, `identity.py`)

### B. Reusable After Refactor (12 components)
- `VersionContract` (`src/intelligence/contracts.py`): Extended with Section 20 fields `rag_version` and `ai_contract_version`.
- `catalog()` (`src/intelligence/microtopics/catalog.py`): Extended with zero-arg default loading from `AppConfig`.
- `ProductionRAGManager` (`src/intelligence/rag/manager.py`): Hardened with retrieval caching, `TemporalEvidencePolicy`, and `RankingBreakdown` attachment.
- `check_chunk_eligibility` (`src/intelligence/rag/eligibility.py`): Refactored to delegate to `TemporalEvidencePolicy`.
- `rank_evidence_chunks` (`src/intelligence/rag/ranking.py`): Refactored to compute and attach typed `RankingBreakdown`.
- `CharacterChunker`, `Chunk` (`src/intelligence/evidence/chunking.py`): Backing implementation for `Chunker`.
- `GeminiProvider` (`src/intelligence/ai/gemini.py`): Integrated with prompt injection boundaries and structured output schemas.
- `AnalysisOutput` (`src/intelligence/ai/schemas.py`): Extended with typed `ClaimType` and `AIAnalysis`.
- `validate_analysis` (`src/intelligence/validation/pipeline.py`): Integrated with typed `ValidationResult` and publishability policies.
- `ApplicationOrchestrator` (`src/intelligence/application/orchestrator.py`): 16-stage orchestration coordinating domain modules.
- `EditionRunner` (`src/intelligence/application/edition_runner.py`): Authoritative edition context and summary lifecycle.
- `ProductionRepository` (`src/intelligence/persistence/repository.py`): Safe atomic staging and rename persistence.

### C. Duplicated / Deprecated / Wrapped (6 components)
- `retrieval.py`: Converted to thin compatibility wrapper delegating completely to `intelligence.rag.manager`.
- `ai.py`: Converted to thin backward-compatible adapter delegating to `intelligence.ai`.
- `pipeline.py`: Converted to thin facade delegating to `ApplicationOrchestrator`.
- `provider.py`: Converted to thin facade delegating to `intelligence.ai`.
- `production.py`: Retained as legacy CLI entry point; refactored to delegate to `ApplicationOrchestrator`.
- `compatibility/legacy.py`: Re-exports legacy symbols without duplicate logic.

### D. Newly Introduced (6 components)
- `TemporalEvidencePolicy` (`src/intelligence/rag/eligibility.py`): Centralized P0 future-data protection and timestamp disambiguation.
- `RankingBreakdown` (`src/intelligence/rag/ranking.py`): Typed multi-factor scoring breakdown persistence.
- `RetrievalCache`, `RetrievalCacheKey` (`src/intelligence/rag/cache.py`): Deterministic retrieval caching keyed by version, query, and cutoff.
- `Chunker` (`src/intelligence/evidence/chunks.py`): Unified chunking interface producing token estimates, offsets, and complete provenance.
- `EvidenceStore`, `LocalEvidenceStore` (`src/intelligence/evidence/store.py`): Persistent evidence storage decoupled from indexing.
- `TokenBudgetManager` (`src/intelligence/ai/token_budget.py`): Token preflight reservation and consumption tracking.
