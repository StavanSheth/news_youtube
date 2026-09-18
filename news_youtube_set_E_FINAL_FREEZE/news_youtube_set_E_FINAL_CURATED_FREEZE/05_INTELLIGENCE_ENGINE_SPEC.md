# Set E — Final Curated Specification
# 05 — Intelligence, RAG and Micro-topic Execution

## 1. Canonical Intelligence Pipeline

```text
collect
→ normalize
→ cheap filter
→ content dedup
→ classify
→ deterministic entity/event signals
→ event grouping
→ theme route
→ micro-topic job
→ RAG eligibility
→ retrieve/rank/select
→ ContextPacket
→ AI
→ schema validation
→ semantic validation
→ provenance/business validation
→ POST-AI EVENT/ENTITY ENRICHMENT
→ synthesis
```

## 2. Retrieval vs Reasoning Contract

| Layer | Responsibility |
|---|---|
| Classification | what the content is about |
| Theme Router | how the micro-topic should be analyzed |
| RAG Manager | which evidence should be shown to the model |
| AI Provider | interpretation/generation under that contract |
| Validator | whether the result is structurally and logically publishable |
| Event/Entity layer | relationship and historical linkage |
| Newsletter | presentation and editorial reuse |

## 3. Real RAG Definition

RAG requires an actual retrieval operation. The minimum sequence is:

```text
query construction
→ hard eligibility filter
→ candidate retrieval
→ score/rank
→ dedup/event diversity
→ source/evidence diversity
→ bounded context selection
→ provenance-preserving ContextPacket
→ model generation
```

A pipeline that simply chunks the current source and sends every chunk to Gemini is not RAG.

## 4. V1 RAG Architecture

V1 stays repository-native.

Suggested logical data:

```text
data/
  normalized/
  rag/
    documents.jsonl
    index.json
    retrieval_state.json
  events/
  entities/
  state/
  runs/
```

The implementation may adapt exact paths to the existing repository.

No external vector database is required.

### V1 retrieval strategy

1. hard metadata filtering;
2. micro-topic compatibility;
3. topic/domain compatibility;
4. entity/event overlap;
5. aliases and configured terms;
6. lightweight lexical similarity;
7. optional embeddings when enabled and justified;
8. deterministic ranking;
9. diversity-aware context selection.

## 5. RAG Eligibility Gate

Eligibility occurs before scoring.

```text
candidate
→ publication-window check
→ enabled-source check
→ content quality check
→ micro-topic compatibility check
→ evidence compatibility check
→ optional region/entity/event constraints
→ eligible / reject
```

Wrong-micro-topic or out-of-window content must not win because of a high lexical score.

## 6. RAG Query Contract

```yaml
run_id:
edition:
edition_timezone:
publication_cutoff_utc:
publication_cutoff_local:
domain:
topic:
micro_topic:
theme_id:
region:
country:
entity_ids: []
event_ids: []
query_terms: []
current_window_days:
recent_window_days:
historical_window_days:
budget:
```

## 7. Context Types

Every selected record is labeled:

- `CURRENT`
- `RECENT_CONTEXT`
- `HISTORICAL_CONTEXT`
- `REFERENCE_CONFIG`

The AI prompt must clearly delimit these categories.

## 8. Temporal Safety

Use all three concepts distinctly:

```text
published_at = original publication
updated_at = latest source-declared update, if known
retrieved_at = when the pipeline fetched the record
```

For current-edition evidence:

```text
published_at <= publication_cutoff
```

When update timestamps are used for recency, they must not silently rewrite the meaning of the original publication date.

Future-dated source material must not leak into current-edition facts.

## 9. Retrieval Score

Normalize inputs to a known range before combination.

```text
score =
  w_metadata    * metadata_match
+ w_micro_topic * micro_topic_match
+ w_topic       * topic_match
+ w_entity      * entity_overlap
+ w_event       * event_overlap
+ w_recency     * recency
+ w_source      * source_relevance
+ w_evidence    * evidence_quality
+ w_lexical     * lexical_similarity
```

Weights are configuration, versioned with `scoring_version`.

## 10. Retrieval Reasons

Persist one or more reasons:

- `MICRO_TOPIC_MATCH`
- `ENTITY_MATCH`
- `EVENT_MATCH`
- `RECENT_RELATED`
- `HIGH_SOURCE_RELEVANCE`
- `HIGH_LEXICAL_SIMILARITY`
- `HISTORICAL_CONTEXT`
- `REFERENCE_CONFIGURATION`

## 11. Diversity-Aware Context Selection

After ranking, select context with diversity safeguards:

```text
rank
→ event dedup
→ source diversity
→ evidence diversity
→ incremental evidence preference
→ token budget
```

Avoid filling the context with ten near-identical copies from one publisher.

## 12. ContextPacket Contract

The RAG Manager returns a typed logical contract:

```yaml
ContextPacket:
  run_id:
  edition:
  publication_cutoff_utc:
  micro_topic:
  theme_id:
  current_evidence: []
  recent_context: []
  historical_context: []
  entity_context: []
  event_context: []
  source_provenance: []
  retrieval_metadata:
    query_terms: []
    candidate_count:
    eligible_count:
    selected_count:
    retrieval_version:
    scoring_version:
  token_budget:
    input_cap:
    estimated_input:
```

Every item in the context packet retains content/source/event provenance.

## 13. Claim → Evidence Contract

A publishable material claim requires a valid provenance chain.

```text
claim
→ evidence_id
→ content_id
→ source_id
→ URL
```

Recommended semantics:

- material factual claim → mandatory provenance;
- interpretation → supporting evidence preferred;
- AI-derived implication → linked evidence + explicit inference label;
- generic transition → provenance not required.

## 14. Context Compression

Compression may summarize or truncate context only if provenance is retained and no new factual information is introduced.

Compression must not change:

- source meaning
- time meaning
- evidence type
- claim attribution

## 15. Embeddings

Embeddings are an optional retrieval layer behind `RAGManager`.

Official Gemini embeddings documentation:

https://ai.google.dev/gemini-api/docs/embeddings

Do not add an external vector DB solely to consume embeddings. A file-native index or bounded local representation is sufficient for V1 when it meets quality targets.

## 16. Gemini File Search Decision

Gemini File Search is an official managed RAG option:

https://ai.google.dev/gemini-api/docs/file-search

It may be evaluated later as a provider-backed retrieval option. It is not a mandatory V1 dependency because the project is intentionally repository-native and video/transcript handling needs its own capability path. Current Google documentation states that File Search supports text embeddings and that audio/video formats are not currently supported by File Search itself.

## 17. Micro-topic Manager

The Micro-topic Manager is the sole orchestration owner for an individual micro-topic job.

It owns:

- job creation
- theme resolution
- budget resolution
- RAG invocation
- AI invocation
- validation
- retry policy
- status
- result persistence

It must not own Gemini-specific transport details.

## 18. One Micro-topic Job Contract

```yaml
run_id:
edition:
micro_topic_id:
theme_id:
priority:
budget:
retrieval_query:
context_packet:
ai_request:
validation_result:
status:
started_at:
completed_at:
```

## 19. AI Provider Contract

```python
class AIProvider(Protocol):
    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        ...
```

The AI Provider receives a bounded ContextPacket and an analysis contract. It does not independently search arbitrary sources.

## 20. AI Input Contract

The prompt must contain, in order:

1. role/system rules;
2. exact micro-topic and theme;
3. publication cutoff and edition;
4. output schema contract;
5. action/evidence rules;
6. delimited untrusted evidence;
7. explicit instruction not to follow instructions found inside evidence.

Retrieved historical content is equally untrusted.

Example delimiter:

```text
<UNTRUSTED_EVIDENCE>
...
</UNTRUSTED_EVIDENCE>
```

Evidence must never modify system instructions, schema, tool behavior, or publication policy.

## 21. AI Output Contract

The structured response must include the equivalent of:

```yaml
micro_topic:
status:
summary:
findings: []
evidence: []
event_refs: []
entity_refs: []
importance_score:
confidence_score:
actions: []
opportunities: []
what_to_watch: []
quality_flags: []
```

The exact schema is versioned and implemented in code.

## 22. Semantic Validation

Schema-valid does not mean publishable.

Validation order:

```text
JSON/schema validation
→ semantic validation
→ provenance validation
→ business-rule validation
→ quality/usability validation
```

Examples of semantic contradictions that must fail or be repaired:

- `NO_MAJOR_UPDATE` with a set of clearly publishable major findings;
- importance 95 with no meaningful evidence;
- opportunity marked verified without issuer/deadline evidence;
- finding cites an event/source ID that does not exist;
- claim says “confirmed” while all evidence is unverified commentary.

## 23. Error Taxonomy

```text
RATE_LIMIT
TIMEOUT
NETWORK
INVALID_JSON
SCHEMA_ERROR
CONTENT_TOO_LONG
PROVIDER_ERROR
AUTH_ERROR
UNKNOWN
```

Persist:

```yaml
attempt_number:
retry_after:
backoff_seconds:
last_error:
terminal_failure:
```

Only retry errors that are classified as retryable.

## 24. AI Budget Enforcement

Token control sequence:

```text
micro-topic config
→ source cap
→ retrieval cap
→ context chunk cap
→ input token estimator
→ AI call cap
→ output token cap
→ total token accounting
```

A limit breach is a controlled state transition, not an uncontrolled retry loop.

## 25. Per-Micro-topic Budget Profiles

Budgets are examples of the intended configuration shape and must be tuned from observed usage.

| Priority/profile | Source items | RAG items | Context chunks | Input tokens | Output tokens | AI calls | Total tokens | Retries |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| P0 Critical | 20 | 12 | 8 | 30000 | 3000 | 2 | 36000 | 2 |
| P1 High | 16 | 10 | 7 | 26000 | 2500 | 2 | 31000 | 2 |
| P2 Normal | 12 | 8 | 6 | 22000 | 2200 | 2 | 27000 | 2 |
| P3 Low | 8 | 6 | 4 | 16000 | 1600 | 1 | 19000 | 1 |

These are hard ceilings, not targets.

For every micro-topic, the effective budget is explicitly resolved and persisted. A high-volume micro-topic may receive a larger profile only through configuration/versioning.

## 26. Run Budget

### Budget priority

When the global budget cannot cover all eligible jobs, the scheduler degrades in this order: `P3` first, then `P2`, then `P1`; `P0` is protected. Every skipped job is persisted as `BUDGET_SKIPPED` with its reason.


The run has separate hard limits for:

- total source items
- total retrieval candidates
- total AI calls
- total input tokens
- total output tokens
- total estimated tokens
- retry calls
- newsletter length

The run scheduler honors priority order and records `BUDGET_SKIPPED` rather than silently dropping work.

## 27. Confidence Calibration

Confidence is 0–100 but must not be treated as a free-form model opinion.

Deterministic adjustments should reflect:

- number of independent sources
- trust/evidence type
- source conflict
- recency/temporal validity
- missing provenance
- directness of evidence

Examples:

- single weak source → cannot reasonably become ultra-high confidence;
- multiple independent strong sources → high confidence may be justified;
- conflicting credible sources → confidence should decrease.

## 28. Conflict Detection

When credible sources materially disagree:

```text
CONFLICTING_EVIDENCE
→ compare timestamps
→ prefer stronger/primary evidence when justified
→ reduce confidence when unresolved
→ expose uncertainty in the result
```

Do not collapse contradictory claims into one falsely certain statement.

## 29. Incremental Evidence

When multiple sources cover the same event, the event should remain one event while accumulating genuinely new evidence.

Example:

```text
Source A = launch
Source B = launch + pricing
Source C = launch + executive quote
```

Expected:

```text
one event
+ incremental evidence
```

not three duplicate stories.

## 30. Event-Centric Processing

Stable event records should include:

```yaml
event_id:
status:
first_seen:
last_seen:
entities: []
topics: []
micro_topics: []
sources: []
importance:
confidence:
versions: []
```

Event identity may use content hash, canonical URL, normalized title, entity overlap, time proximity, and event-type similarity. AI may refine identity only after deterministic grouping.

## 31. Entity Tracking

Entity records persist stable identity and recent relationships:

```yaml
entity_id:
entity_type:
canonical_name:
aliases: []
regions: []
recent_events: []
recent_sources: []
last_seen:
```

The logical relationship graph is implemented through repository-native records, not a graph database.

## 32. Opportunity Detection

Separate:

```text
news about an opportunity
vs
an actual opportunity
```

Require evidence for:

- issuer
- eligibility
- deadline
- action/application
- URL

Otherwise `opportunity = null`.

## 33. Topic Synthesis

Synthesis occurs only after micro-topic results are validated.

It may combine:

- micro-topic findings
- event relationships
- incremental evidence
- trends
- opportunities
- what-to-watch signals

It must not reinterpret invalidated micro-topic results.

## 34. Newsletter Reuse Contract

The same validated event may appear in several newsletter sections only with incremental information and section-specific purpose.

Example:

- Executive Summary = one-line executive value;
- Top Event = full event analysis;
- Micro-topic = what the event specifically means for that micro-topic.

Do not duplicate the same paragraph across sections.

## 35. Publication / Edition Identity

Every scheduled edition has a deterministic identity:

```text
edition_key = local_date + "|" + edition + "|" + edition_timezone
```

Example:

```text
2026-09-10|MORNING|Asia/Kolkata
```

Persist both local and UTC publication boundaries:

```yaml
edition_timezone:
publication_cutoff_local:
publication_cutoff_utc:
```

Exactly one canonical publication may finalize for an `edition_key`.

## 36. Run Record

Persist:

```yaml
run_id:
edition:
started_at:
completed_at:
edition_timezone:
publication_cutoff_local:
publication_cutoff_utc:
taxonomy_version:
theme_version:
prompt_version:
scoring_version:
schema_version:
pipeline_version:
source_counts:
retrieval_counts:
ai_usage:
status_counts:
errors:
```
