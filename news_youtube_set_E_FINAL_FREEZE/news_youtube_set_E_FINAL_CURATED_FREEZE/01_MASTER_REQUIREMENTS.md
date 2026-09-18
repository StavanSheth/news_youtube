# Set E — Final Curated Specification
# 01 — Master Requirements

## 1. Purpose

This document is the authoritative product contract for `StavanSheth/news_youtube`.

The system is a repository-native Python daily intelligence pipeline that turns configured News and YouTube inputs into evidence-backed, micro-topic-specific intelligence and exactly two daily newsletter editions.

Primary goals, in order:

1. Correctness
2. Traceability and provenance
3. Micro-topic accuracy
4. Evidence quality
5. Useful, specific output
6. Reliability
7. AI/API cost control
8. Simplicity
9. Extensibility

Feature count is not a success metric.

## 2. Non-Negotiable Infrastructure Constraints

Use the existing repository stack and GitHub Actions execution model.

Do not introduce for V1:

- SQL/SQLite/PostgreSQL/MySQL or another database service
- Redis/Kafka or a queueing platform
- Kubernetes/Docker infrastructure
- Microservice deployment
- Always-on server infrastructure
- Telegram delivery
- Frontend/mobile application

GitHub repository files are the persistence/archive layer. SMTP is the delivery mechanism for email.

Embeddings may be used as an optional retrieval enhancement. A vector database is not required.

## 3. Editions

Exactly two business editions exist:

- `MORNING` — start-of-day intelligence
- `NIGHT` — end-of-day intelligence

Edition schedule times are configuration. Edition identity is business logic.

Each run must carry both local and UTC cutoff information:

```yaml
edition: MORNING | NIGHT
edition_timezone: Asia/Kolkata
publication_cutoff_local: <timestamp>
publication_cutoff_utc: <timestamp>
```

## 4. Primary Streams

### 4.1 News Intelligence

Configured RSS/API/public/official/specialist sources are collected and normalized. The system identifies meaningful events and analyzes them by exact micro-topic and theme.

News intelligence must answer, where evidence permits:

- What happened?
- What changed?
- What is confirmed, reported, claimed, or uncertain?
- Which entities/events are affected?
- Why does it matter?
- What are the implications and risks?
- What should be watched next?

### 4.2 YouTube / Video Intelligence

V1 processes only explicitly configured YouTube channels.

The following are prohibited for normal V1 processing:

- unrestricted global YouTube discovery
- automatic channel discovery
- recommendation-based ingestion
- unrelated channel ingestion merely because a video matches a keyword

Supported content types can include podcasts, interviews, case studies, tutorials, technical explainers, demos, news reports, commentary, lectures/talks, conferences, and documentaries.

Video intelligence focuses on what was actually said or demonstrated: ideas, arguments, evidence, examples, frameworks, methods, workflows, tools, experiments, predictions, limitations, contradictions, practical application, and justified actions.

## 5. Canonical Information Model

Primary classification hierarchy:

```text
Domain
  ↓
Topic
  ↓
Micro-topic
  ↓
Theme
  ↓
Analysis Contract
```

Cross-cutting relationships:

```text
Content ↔ Source ↔ Event ↔ Entity ↔ Domain/Topic/Micro-topic
```

Required dimensions where applicable:

- region
- country
- content type
- event type
- report type
- importance
- confidence
- evidence type
- provenance
- action type
- source trust tier

## 6. Canonical Processing Pipeline

All documentation and implementation must use this one pipeline unless a documented exception exists:

```text
COLLECT
  ↓
NORMALIZE
  ↓
CHEAP FILTER
  ↓
CONTENT DEDUPLICATION
  ↓
CLASSIFY (domain/topic/micro-topic)
  ↓
DETERMINISTIC ENTITY / EVENT SIGNALS
  ↓
EVENT GROUPING
  ↓
THEME ROUTING
  ↓
MICRO-TOPIC MANAGER
  ↓
RAG ELIGIBILITY FILTER
  ↓
RAG RETRIEVAL + RANKING + DIVERSITY + BUDGET
  ↓
CONTEXT PACKET
  ↓
AI PROVIDER
  ↓
SCHEMA VALIDATION
  ↓
SEMANTIC VALIDATION
  ↓
PROVENANCE / BUSINESS-RULE VALIDATION
  ↓
EVENT / ENTITY / OPPORTUNITY / TREND ENRICHMENT
  ↓
TOPIC SYNTHESIS
  ↓
NEWSLETTER ASSEMBLY
  ↓
MARKDOWN + HTML
  ↓
SMTP
  ↓
GIT ARCHIVE
```

This ordering resolves the prior inconsistency around whether event/entity work happens before or after AI. Cheap deterministic signals and grouping occur before expensive AI. AI may enrich validated event/entity relationships afterward.

## 7. Component Ownership

| Component | Owns | Does not own |
|---|---|---|
| Source collectors | collection, source metadata, normalization handoff | final intelligence |
| Classifier | domain/topic/micro-topic assignment | reasoning |
| Theme Router | exact theme resolution and fallback | retrieval/model calls |
| Micro-topic Manager | one micro-topic job, scheduling, budget, status, orchestration | model internals |
| RAG Manager | eligibility, retrieval, ranking, diversity, context, provenance | interpretation |
| AI Provider | provider/API call and structured response | retrieval, persistence |
| Validator | schema, semantic, provenance, business rules | collection |
| Event/Entity layer | deterministic linkage + history + post-AI enrichment | presentation |
| Newsletter builder | selection, reuse, structure, editorial budgets | source/API calls |
| State/archive | operational history and durable artifacts | business interpretation |

There must not be two independent owners for the same responsibility.

## 8. AI-Last Rule

AI is called only after cheap deterministic work has reduced the search space and an isolated micro-topic context packet is available.

The normal AI unit is one micro-topic job, not one giant taxonomy-wide request.

The AI must never receive every enabled micro-topic and all source material at once.

## 9. Micro-topic Isolation Rule

For a micro-topic `M`:

```text
M
 → exact theme
 → M-specific query
 → M-specific eligible evidence
 → M-specific RAG context
 → M-specific AI analysis
 → validation
 → M-specific result
```

Evidence retrieved only for another micro-topic must not enter `M`'s context packet unless it is explicitly marked as shared event/entity context and is independently relevant to `M`.

## 10. No-Update Semantics

`NO_MAJOR_UPDATE` is not a synonym for zero retrieval results.

A defensible `NO_MAJOR_UPDATE` requires that the micro-topic was actually checked, candidate material was evaluated, duplicates/events were considered, and no item passed the configured publication threshold.

Canonical statuses:

- `MAJOR_UPDATE`
- `MINOR_UPDATE`
- `NO_MAJOR_UPDATE`
- `NO_RELEVANT_CONTENT`
- `INSUFFICIENT_EVIDENCE`
- `BUDGET_SKIPPED`
- `TRANSCRIPT_UNAVAILABLE` for video-specific cases
- `ERROR`

A budget-skipped micro-topic must never be represented as `NO_MAJOR_UPDATE`.

## 11. Evidence and Claim Contract

Material factual claims require provenance:

```text
claim
 → evidence_id
 → content_id
 → source_id
 → source URL
```

Interpretation should normally retain supporting evidence. AI-derived implications must be labeled as inference rather than presented as source fact.

Generic transitions do not require citation.

Evidence types are distinct from source trust:

- `PRIMARY_OFFICIAL`
- `REPORTED`
- `EXPERT_COMMENTARY`
- `SECONDARY_ANALYSIS`
- `LEAD_ONLY`
- `AI_INFERENCE`

Trust tier is a ranking signal; it is never equivalent to truth.

## 12. AI Budget Contract

Every enabled micro-topic resolves to explicit hard limits:

```yaml
max_source_items:
max_rag_items:
max_context_chunks:
max_input_tokens:
max_output_tokens:
max_ai_calls:
max_total_tokens:
max_retries:
priority: P0 | P1 | P2 | P3
```

Global run budgets are separate hard ceilings.

Suggested priority behavior when the global run budget is constrained:

```text
P3 skipped first
P2 next
P1 next
P0 protected
```

The scheduler must persist why a job was skipped or truncated.

## 13. Publication Success Contract

A publication is considered successful only when the edition has a validated rendered artifact, a delivery state of `DELIVERY_CONFIRMED`, and a durable archive outcome of `ARCHIVED` or an explicitly recorded repair state that has not been misrepresented as complete.

The canonical publication identity is `edition_key`, not `run_id` alone:

```text
YYYY-MM-DD|EDITION|EDITION_TIMEZONE
```

Email delivery uncertainty is distinct from failure. Archive repair must never create duplicate delivery.

## 14. RAG Contract

RAG means:

```text
query construction
→ hard eligibility filter
→ candidate retrieval
→ scoring/ranking
→ dedup/event diversity
→ source/evidence diversity
→ bounded context selection
→ provenance-preserving ContextPacket
→ model generation
```

Chunking alone is not RAG.

V1 may use repository/file-native retrieval and deterministic lexical ranking. Optional embeddings may be added behind the same interface when measured quality justifies them.

## 15. Quality Direction

The newsletter must optimize for high signal / low noise.

Avoid generic statements such as “AI continues to evolve rapidly” unless they are directly tied to a specific development and evidence.

Every major finding should make clear:

```text
What happened?
Why does it matter?
What changes because of it?
```

A justified action may then be added.

## 16. Action Attribution

Actions must be classified as:

- `SOURCE_STATED`
- `AI_DERIVED`
- `AI_DERIVED_EXPERIMENT`
- `PERSONALIZED_APPLICATION`

Do not present AI-derived advice as though the source said it.

## 17. Opportunities

A funding announcement is not automatically an opportunity.

An opportunity must be evidenced and, where applicable, include:

- issuer
- eligibility
- deadline
- application/action
- application URL
- opportunity status

Statuses:

- `VERIFIED`
- `PARTIALLY_VERIFIED`
- `UNVERIFIED`
- `EXPIRED`

Unsupported opportunity details must be null, not invented.

## 18. Production Non-Goals for V1

Do not introduce advanced infrastructure merely to make the architecture look larger.

Deferred examples:

- external vector database
- graph database
- multi-agent swarm
- advanced workflow queue
- semantic-search platform
- advanced analytics service
- trend visualization platform

The logical knowledge graph relationship model remains valid without a graph database.

## 19. Definition of Done

The system is production-ready only when all P0 requirements pass and required P1 quality gates pass.

P0 includes at minimum:

- canonical pipeline implemented
- exact micro-topic routing
- real RAG retrieval execution
- future-data protection
- provenance validation
- semantic/business validation
- duplicate event suppression
- no-update integrity
- YouTube configured-channel restriction
- secure secret handling
- SMTP correctness
- critical acceptance tests

P1 includes source diversity, confidence calibration, conflict detection, genericness/usefulness gates, and performance optimization.
