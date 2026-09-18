# Phase 2 Target Architecture Specification

## 1. System Philosophy & Non-Negotiable Boundaries

The system is a single, repository-native Python intelligence application scheduled by GitHub Actions.
It operates without external vector databases, message queues, container clusters, or always-on servers.

### Core Architecture Rules:
1. **AI-Last**: Cheap deterministic filtering, deduplication, classification, and event grouping occur before any expensive RAG or AI calls.
2. **Micro-Topic Isolation**: Each micro-topic job operates in an isolated context envelope with explicit `EvidenceScope`.
3. **One Concept → One Authoritative Implementation**: Every pipeline stage has a single authoritative owner; compatibility wrappers only exist where external contracts or test suites require them.
4. **Dependency Inversion**: Domain models and business logic never depend on infrastructure (no direct `os.environ`, `datetime.now()`, `requests.get()`, or `genai.Client` in domain logic).

---

## 2. Canonical Pipeline Dataflow

```text
SOURCE (RSS / Configured YouTube Channels)
  ↓
COLLECT (ingestion/collectors)
  ↓
NORMALIZE (canonical SourceItem format)
  ↓
CHEAP FILTER (freshness, publication cutoff, channel restrictions)
  ↓
CONTENT DEDUPLICATION (deterministic content_id and content_hash)
  ↓
CLASSIFY (domain / topic / micro-topic signals and scoring)
  ↓
DETERMINISTIC ENTITY / EVENT SIGNALS (exact keyword & pattern matching)
  ↓
EVENT GROUPING (corroboration, related sources, event_id)
  ↓
THEME ROUTING (precedence order, specific profile, controlled fallback)
  ↓
MICRO-TOPIC MANAGER (budget check, pre-execution reservation)
  ↓
RAG ELIGIBILITY FILTER (publication window, source eligibility, scope match)
  ↓
RAG RETRIEVAL (BM25L lexical + dense vector pseudo-embeddings)
  ↓
FUSION & RANKING (RRF k=60, 6-factor composite scoring)
  ↓
DIVERSITY & CONTEXT BUDGET (source diversity, character & token budgeting)
  ↓
CONTEXT PACKET (immutable frozen dataclass, SHA-256 integrity hash)
  ↓
GEMINI PROVIDER (structured output, prompt boundary, Pydantic validation)
  ↓
SCHEMA VALIDATION (structural constraints, types, ranges)
  ↓
SEMANTIC VALIDATION (coverage, specificity, genericness, contradiction)
  ↓
PROVENANCE VALIDATION (fail-closed citation link to evidence and source ID)
  ↓
BUSINESS-RULE VALIDATION (future data, cutoff, channel constraints)
  ↓
USEFULNESS VALIDATION (filler phrase detection, actionable insight check)
  ↓
POST-AI ENRICHMENT (entity/opportunity linkage, corroboration scoring)
  ↓
TOPIC SYNTHESIS (multi-story roll-up and importance weighting)
  ↓
NEWSLETTER ASSEMBLY (NewsletterModel)
  ↓
MARKDOWN + HTML (independent renderers)
  ↓
SMTP DELIVERY (delivery idempotency via edition_key + newsletter_hash)
  ↓
GIT ARCHIVE & RUN MANIFEST (atomic state writes, durable retention)
```

---

## 3. Subsystem Architecture

### 3.1 Application Layer (`src/intelligence/application/`)
- `pipeline.py`: The single canonical orchestrator executing the end-to-end pipeline.
- `edition_runner.py`: Manages MORNING / NIGHT edition lifecycle, cutoffs, and execution context.
- `lifecycle.py`: Run initialization, checkpointing, and safe recovery.

### 3.2 Evidence & Chunking (`src/intelligence/evidence/`)
- `chunking.py`: `ChunkingStrategy`, `CharacterChunker`, `SentenceChunker`, `Chunk`.
- `scope.py`: `EvidenceScope`, `EvidenceScopeBuilder` (enforcing authorization boundaries).

### 3.3 Production RAG (`src/intelligence/rag/`)
- `manager.py`: Authoritative `ProductionRAGManager`.
- `index.py`: Deterministic BM25L (`rank-bm25`) + local deterministic dense vector index.
- `fusion.py`: Reciprocal Rank Fusion ($k=60$) with deterministic lexical rank tie-breaking.
- `retrieval.py`: Candidate eligibility filtering, temporal freshness gating, and multi-factor composite scoring.
- `diversity.py`: Source diversity constraints and channel balancing.
- `packet.py`: Frozen immutable `ContextPacket` with SHA-256 hash.
- `provenance.py`: Provenance chain verification.

### 3.4 AI Layer (`src/intelligence/ai/`)
- `base.py`: `AIProvider` Protocol, `AIRequest`, `AIResponse`.
- `schemas.py`: Pydantic `AnalysisOutput`, `Fact`, `Inference`, `Action`, `Change`.
- `gemini.py`: Authoritative `GeminiProvider` using official `google-genai` client, strict schema enforcement, and untrusted source boundary demarcation.
- `usage.py`: Token counting via `count_tokens`, usage accounting (`prompt_token_count`, `candidates_token_count`), and cost tracking.
- `retry.py` & `errors.py`: Categorized failures and bounded exponential backoff.
- `dry_run.py`: Deterministic provider for fixtures and CI dry-runs.

### 3.5 Validation Pipeline (`src/intelligence/validation/`)
- `pipeline.py`: Authoritative 5-stage sequential validation (`SCHEMA` $\to$ `SEMANTIC` $\to$ `PROVENANCE` $\to$ `BUSINESS` $\to$ `USEFULNESS`).
- Strict fail-closed rules on uncited claims or mismatched evidence IDs.

### 3.6 Budgeting (`src/intelligence/budgets/`)
- `manager.py`: Atomic reservation lifecycle (`reserve` $\to$ `consume` $\to$ `release`) with P0 priority pools and audit traces on skip.

### 3.7 Persistence & Recovery (`src/intelligence/persistence/`)
- `paths.py`: Canonical file paths.
- `atomic.py`: Safe atomic file writing (`temporary file` $\to$ `fsync` $\to$ `atomic rename`).
- `manifest.py`: Run manifest tracking execution status, version hashes, counts, and budgets.
- `state.py`: Repository processing state and idempotency tracking.

### 3.8 Newsletter & Rendering (`src/intelligence/newsletter/`)
- `assembler.py`: Assembles validated intelligence stories into `NewsletterModel`.
- `markdown.py`: Independent Markdown renderer.
- `html.py`: Independent HTML renderer with semantic tags and CSS styling.
- `delivery.py`: Idempotent email dispatch.

### 3.9 Infrastructure (`src/intelligence/infrastructure/`)
- `clock.py`: Centralized clock abstraction (`Clock`, `SystemClock`, `FixedClock`).
- `config.py`: Unified configuration loader for YAML configs (`models.yaml`, `budgets.yaml`, `application.yaml`).
