# Phase 2 Code Map & Module Ownership Audit

## 1. Classification Categories
Every Python module under `src/intelligence/` is evaluated and classified into one of the following authoritative states:
- **AUTHORITATIVE**: The canonical, single source of truth for its designated responsibility.
- **COMPATIBILITY**: Preserved facade or adapter maintaining public API and test backwards-compatibility while delegating to the authoritative engine.
- **DUPLICATE**: Contains competing or redundant logic that has been or will be consolidated into an authoritative module.
- **LEGACY**: Pre-Phase 2 code kept temporarily for backward compatibility.
- **ORPHANED**: Unused code with no runtime or test references.
- **UTILITY**: Helper or cross-cutting utility functions.
- **TEST SUPPORT**: Module existing primarily to support test assertions and fixture evaluations.

---

## 2. Comprehensive Module Mapping

| Current File | Responsibility | Authoritative? | Duplicate Of | Replacement / Target | Action |
|:---|:---|:---:|:---|:---|:---|
| `src/intelligence/__init__.py` | Package root export | COMPATIBILITY | None | Top-level exports | KEEP |
| `src/intelligence/ai.py` | Legacy Gemini analyzer | COMPATIBILITY | `src/intelligence/ai/gemini.py` | `src/intelligence/ai/gemini.py` | REFACTOR to delegate to `ai/gemini.py` |
| `src/intelligence/benchmark.py` | Benchmark evaluation | TEST SUPPORT | None | None | KEEP |
| `src/intelligence/classification.py` | Relevance & scoring | AUTHORITATIVE | None | `src/intelligence/classification.py` | KEEP (reusable classification primitives) |
| `src/intelligence/config.py` | Configuration loader | AUTHORITATIVE | None | `src/intelligence/infrastructure/config.py` | CONSOLIDATE into infrastructure |
| `src/intelligence/contracts.py` | Domain contracts & types | AUTHORITATIVE | None | `src/intelligence/domain/contracts.py` | KEEP as canonical domain contracts |
| `src/intelligence/coverage.py` | 8-State coverage ledger | AUTHORITATIVE | None | `src/intelligence/coverage.py` | KEEP (authoritative coverage machine) |
| `src/intelligence/emailer.py` | SMTP digest dispatch | AUTHORITATIVE | None | `src/intelligence/publication/delivery.py` | REFACTOR to use publication delivery |
| `src/intelligence/enrichment.py` | Entity/Opportunity signals | AUTHORITATIVE | None | `src/intelligence/enrichment.py` | KEEP |
| `src/intelligence/events.py` | Event grouping & identity | AUTHORITATIVE | None | `src/intelligence/events.py` | KEEP (deterministic event grouping) |
| `src/intelligence/evidence_projection.py` | Scope projection | UTILITY | None | `src/intelligence/evidence/` | KEEP & link with evidence scope |
| `src/intelligence/evidence_scope.py` | Micro-topic scope model | AUTHORITATIVE | None | `src/intelligence/evidence/scope.py` | KEEP as authoritative scope object |
| `src/intelligence/identity.py` | Deterministic ID generators | AUTHORITATIVE | None | `src/intelligence/identity.py` | KEEP (content, source, event IDs) |
| `src/intelligence/ingestion.py` | RSS feed parsing & fetch | AUTHORITATIVE | None | `src/intelligence/ingestion/` | KEEP |
| `src/intelligence/manager.py` | Micro-topic orchestrator | AUTHORITATIVE | None | `src/intelligence/manager.py` | KEEP & refine interfaces |
| `src/intelligence/models.py` | Data models & envelopes | AUTHORITATIVE | None | `src/intelligence/models.py` | KEEP |
| `src/intelligence/newsletter.py` | Newsletter data model | AUTHORITATIVE | None | `src/intelligence/newsletter/` | KEEP |
| `src/intelligence/persistence.py` | Persistence paths & I/O | AUTHORITATIVE | None | `src/intelligence/persistence/` | ENHANCE with atomic writes |
| `src/intelligence/pipeline.py` | Pipeline entrypoint | COMPATIBILITY | `src/intelligence/application/pipeline.py` | `src/intelligence/application/pipeline.py` | REFACTOR to delegate to `application/pipeline.py` |
| `src/intelligence/production.py` | Monolithic pipeline runner | COMPATIBILITY | `src/intelligence/application/pipeline.py` | `src/intelligence/application/pipeline.py` | REFACTOR orchestration to `application/pipeline.py` |
| `src/intelligence/profiles.py` | Profile loading helpers | COMPATIBILITY | `microtopics/profiles.py` | `microtopics/profiles.py` | KEEP as compatibility wrapper |
| `src/intelligence/provider.py` | AI provider protocol & Gemini | COMPATIBILITY | `src/intelligence/ai/gemini.py` | `src/intelligence/ai/` | DELEGATE to `src/intelligence/ai/` |
| `src/intelligence/quality.py` | Quality scoring & hard gates | AUTHORITATIVE | None | `src/intelligence/quality.py` | KEEP (authoritative 9-dimension engine) |
| `src/intelligence/registry.py` | Source registry | AUTHORITATIVE | None | `src/intelligence/registry.py` | KEEP |
| `src/intelligence/render.py` | Markdown & HTML rendering | COMPATIBILITY | `src/intelligence/newsletter/` | `src/intelligence/newsletter/` | REFACTOR into dedicated renderers |
| `src/intelligence/retrieval.py` | Retrieval facade | COMPATIBILITY | `src/intelligence/rag/retrieval.py` | `src/intelligence/rag/` | DELEGATE 100% to `src/intelligence/rag/` |
| `src/intelligence/schema.py` | Analysis schema normalization | COMPATIBILITY | `src/intelligence/ai/schemas.py` | `src/intelligence/ai/schemas.py` | DELEGATE to Pydantic/ai schemas |
| `src/intelligence/sources.py` | YouTube source discovery | AUTHORITATIVE | None | `src/intelligence/sources.py` | KEEP (configured-channel enforcement) |
| `src/intelligence/source_validation.py` | Source health validation | AUTHORITATIVE | None | `src/intelligence/source_validation.py` | KEEP |
| `src/intelligence/state.py` | Repository state tracking | AUTHORITATIVE | None | `src/intelligence/persistence/state.py` | CONSOLIDATE into persistence |
| `src/intelligence/statuses.py` | Domain status enums | AUTHORITATIVE | None | `src/intelligence/statuses.py` | KEEP |
| `src/intelligence/budgets/manager.py` | Budget lifecycle manager | AUTHORITATIVE | None | `src/intelligence/budgets/manager.py` | KEEP (reserve/consume/release model) |
| `src/intelligence/budgets/__init__.py` | Budgets package init | AUTHORITATIVE | None | None | KEEP |
| `src/intelligence/microtopics/*` | Micro-topics subsystem | AUTHORITATIVE | None | None | KEEP (modularized in Phase 2A) |
| `src/intelligence/themes/*` | Themes subsystem | AUTHORITATIVE | None | None | KEEP (modularized in Phase 2A) |
| `src/intelligence/rag/*` | Production Hybrid RAG | AUTHORITATIVE | None | None | KEEP (index, fusion, retrieval, packet, provenance) |
| `src/intelligence/validation/*` | 5-Stage validation pipeline | AUTHORITATIVE | None | None | KEEP (schema, semantic, provenance, business, usefulness) |
| `src/intelligence/publication/*` | Archive, delivery, idempotency | AUTHORITATIVE | None | None | KEEP |

---

## 3. Consolidation Directives
1. **Pipeline Orchestration**: `src/intelligence/application/pipeline.py` will become the sole canonical pipeline executor. `src/intelligence/production.py` and `src/intelligence/pipeline.py` delegate to it.
2. **AI Provider**: `src/intelligence/ai/` will house the single authoritative `GeminiProvider` implementation, `AnalysisOutput` Pydantic schemas, retry logic, and token accounting. `src/intelligence/provider.py` and `src/intelligence/ai.py` delegate to `src/intelligence/ai/`.
3. **Retrieval**: `src/intelligence/rag/` is the single authoritative RAG implementation. `src/intelligence/retrieval.py` delegates 100% to it.
4. **Time & System Abstraction**: `src/intelligence/infrastructure/clock.py` centralizes all UTC/local timestamps and provides clock injection.
