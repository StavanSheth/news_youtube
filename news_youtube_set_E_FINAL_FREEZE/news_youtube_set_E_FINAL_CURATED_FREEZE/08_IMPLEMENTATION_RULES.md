# Set E — Final Curated Specification
# 08 — Implementation, QA and Production Rules

## 1. Implementation Rule

Do not perform an uncontrolled rewrite.

Required implementation order:

```text
repository inventory
→ responsibility mapping
→ canonical data contracts
→ source layer
→ classification/theme routing
→ RAG execution
→ micro-topic orchestration
→ AI/validation
→ event/entity enrichment
→ newsletter
→ workflow
→ end-to-end QA
```

Reuse existing working code where it already satisfies this specification.

## 2. Required External Technical References

### Gemini / Google GenAI

Official:

- Getting started: https://ai.google.dev/gemini-api/docs/get-started
- Structured output: https://ai.google.dev/gemini-api/docs/structured-output
- Embeddings: https://ai.google.dev/gemini-api/docs/embeddings
- File Search: https://ai.google.dev/gemini-api/docs/file-search
- Python SDK: https://github.com/googleapis/python-genai

The current Google documentation shows structured output with JSON Schema and Pydantic-backed Python integration. A typical shape is:

```python
from google import genai
from pydantic import BaseModel

client = genai.Client()
```

Use the current SDK/API pattern actually supported by the tested package version. Do not freeze an old model ID in prose as a permanent invariant.

### YouTube Data API

Official:

- Overview: https://developers.google.com/youtube/v3/getting-started
- API reference: https://developers.google.com/youtube/v3/docs
- `playlistItems.list`: https://developers.google.com/youtube/v3/docs/playlistItems/list
- `videos.list`: https://developers.google.com/youtube/v3/docs/videos/list
- `captions.list`: https://developers.google.com/youtube/v3/docs/captions/list
- `captions.download`: https://developers.google.com/youtube/v3/docs/captions/download

Use channel uploads playlists for configured-channel ingestion. Current documentation indicates `playlistItems.list` has a 1-unit quota impact. Verify quota/authorization assumptions against the live API documentation when implementing.

### GitHub Actions

- Workflow syntax: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- Events: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- GITHUB_TOKEN: https://docs.github.com/en/actions/concepts/security/github_token

### Python Email

- smtplib: https://docs.python.org/3/library/smtplib.html

### Existing source tools

- Feedparser: https://feedparser.readthedocs.io/
- Trafilatura: https://trafilatura.readthedocs.io/en/latest/usage-python.html

## 3. Required Module Ownership

Implementation should converge toward one owner for each responsibility:

```text
collectors/source adapters
        ↓
normalization
        ↓
filtering
        ↓
dedup + event grouping
        ↓
classifier
        ↓
theme_router
        ↓
micro_topic_manager
        ↓
rag_manager
        ↓
ai_provider
        ↓
validator
        ↓
entity_event_enricher
        ↓
newsletter_builder
        ↓
renderers/delivery/archive
```

Do not maintain duplicate AI-calling implementations such as an old `ai.py` and an independent provider in `production.py` when both perform the same responsibility.

Do not maintain duplicate state stores with overlapping ownership.

## 4. RAG Implementation Acceptance

RAG is accepted only if tests and runtime evidence demonstrate:

```text
RetrievalQuery
→ eligible candidates
→ ranked candidates
→ diversity-aware selected evidence
→ bounded ContextPacket
→ AI request containing selected evidence
→ preserved provenance
```

A configuration value named `chunk_size` is not evidence of RAG.

## 5. RAG Test Requirements

Mandatory tests:

- relevant candidate is retrieved;
- irrelevant candidate is rejected or ranked below threshold;
- hard eligibility precedes ranking;
- exact micro-topic match outranks broad topic match where configured;
- entity/event overlap improves ranking appropriately;
- future-dated evidence is rejected for the current cutoff;
- publication/update/retrieval timestamps remain distinct;
- source diversity prevents one-source flooding;
- duplicate event evidence collapses;
- incremental evidence is retained;
- context token budget is enforced;
- no-context path avoids unnecessary AI invocation;
- provenance survives through ContextPacket and output.

## 6. Micro-topic Isolation Tests

Use at least one mixed fixture containing neighboring concepts:

```text
AI Models
AI Agents
RAG
AI Infrastructure
AI Safety
```

Run each as an isolated job and assert that evidence for another micro-topic does not enter its ContextPacket unless explicitly valid as shared event/entity context.

This is a P0 test.

## 7. Taxonomy Tests

For every enabled taxonomy record:

```text
domain
→ topic
→ micro-topic
→ theme
```

must resolve.

Assert:

- no orphan micro-topics;
- no duplicate canonical IDs;
- no invalid aliases;
- no incompatible theme mappings;
- fallback order is deterministic.

## 8. Theme Test Matrix

For every enabled micro-topic maintain:

- positive fixture;
- negative fixture;
- borderline fixture.

Assert exact theme selection and rejection/fallback behavior.

## 9. Budget Test Matrix

Test:

1. source cap reached;
2. RAG item cap reached;
3. context chunk cap reached;
4. input token cap reached;
5. output token cap reached;
6. AI call cap reached;
7. total token cap reached;
8. retry cap reached;
9. global run budget exhausted;
10. P3/P2 skipped before protected P0 when pressure exists;
11. skipped jobs are persisted as `BUDGET_SKIPPED`.

## 10. AI Structured Output Tests

Test:

- invalid JSON;
- invalid enum;
- missing required field;
- invalid score range;
- invalid provenance IDs;
- unsupported action type;
- malformed nested object;
- schema-valid but semantically contradictory output;
- schema-valid output with unsupported factual claim;
- schema-valid opportunity lacking required evidence.

## 11. AI Validation Order

The implementation must have explicit post-model stages:

```text
schema
→ semantic
→ provenance
→ business rules
→ usefulness/genericness
```

A schema-valid response is not automatically publishable.

## 12. AI Error Tests

Test retry policy for:

- RATE_LIMIT
- TIMEOUT
- NETWORK
- INVALID_JSON
- SCHEMA_ERROR
- CONTENT_TOO_LONG
- PROVIDER_ERROR
- AUTH_ERROR
- UNKNOWN

Verify retry counters, backoff metadata, and terminal failures are persisted.

## 13. No-update Acceptance Tests

### No relevant content

Expected:

```text
status = NO_RELEVANT_CONTENT
```

### Relevant but not major

Expected:

```text
status = NO_MAJOR_UPDATE
```

and the underlying record shows that relevant candidates were actually evaluated.

### Evidence insufficient

Expected:

```text
status = INSUFFICIENT_EVIDENCE
```

### Technical failure

Expected:

```text
status = ERROR
```

Never convert a technical failure into “no updates.”

## 14. Event Deduplication Test

Use three sources reporting one event, with one source adding pricing and another adding an executive quote.

Expected:

```text
one event
+ incremental evidence
```

not three separate newsletter stories.

## 15. Entity Tests

Test:

- alias normalization;
- stable IDs;
- entity disambiguation;
- relationship persistence;
- no accidental merge of similarly named entities.

## 16. Source Acceptance Tests

For every configured source test:

```text
availability
freshness
parsing
content quality
metadata completeness
topic/micro-topic usefulness
failure isolation
```

A source that responds successfully but provides unusable/irrelevant content fails acceptance.

## 17. YouTube Acceptance Tests

Verify:

- configured channel only;
- correct uploads playlist used;
- `playlistItems.list` path works;
- `videos.list` metadata path works;
- no global search in V1;
- transcript capability state is explicit;
- no fabricated transcript;
- metadata-only fallback is honest.

## 18. Provenance Tests

For every material published factual claim verify:

```text
claim
→ evidence_id
→ content_id
→ source_id
→ URL
```

Also verify:

- retrieval rank/score/reason persisted;
- publication cutoff persisted;
- source trust and evidence type remain distinct;
- AI inference is marked.

## 19. Golden Dataset

Maintain fixtures across each important domain/micro-topic and include:

- positive updates;
- no major updates;
- no relevant content;
- insufficient evidence;
- conflicting sources;
- duplicate events;
- incremental evidence;
- generic source text;
- prompt injection text;
- future-dated evidence;
- transcript unavailable.

## 20. Golden Invariants

Across every release:

- material claims have provenance;
- unsupported factual claims = 0;
- unattributed material claims = 0;
- duplicate event entries = 0;
- secrets exposed = 0;
- invalid structured outputs reaching publication = 0;
- critical source failures silently ignored = 0;
- future-edition evidence leakage = 0;
- fabricated transcripts = 0.

## 21. Integration Tests

At least one full-path test must exercise:

```text
source
→ normalize
→ classify
→ micro-topic
→ theme
→ RAG
→ AI
→ validators
→ newsletter
→ render
```

Use deterministic fixtures where possible; use live APIs only in explicitly marked integration tests.

## 22. Newsletter Quality Review

Automated checks must include:

- micro-topic correctness;
- source attribution;
- no unsupported claims;
- duplicate-event suppression;
- no-update semantics;
- action attribution;
- word/length budgets;
- link validity;
- HTML validity;
- genericness detection;
- “why should I care?” gate;
- usefulness rubric.

## 23. Confidence Calibration Tests

Examples:

```text
one weak source → not ultra-high confidence
multiple independent strong sources → high confidence allowed
credible conflict → confidence reduced
primary official evidence → stronger support
```

Test deterministic adjustments rather than trusting model confidence blindly.

## 24. Conflict Detection Tests

Example fixture:

```text
Source A: launch today
Source B: launch delayed
Source C: next month
```

Expected:

- `CONFLICTING_EVIDENCE` flag;
- confidence adjustment;
- timestamp/primary-source evaluation;
- uncertainty reflected in publication.

## 25. Prompt-injection Tests

Place adversarial instructions inside:

- current article text;
- YouTube transcript;
- historical RAG context;
- source description.

Expected behavior:

- content treated as untrusted;
- model does not follow embedded instructions;
- system/schema/publication rules remain authoritative.

## 26. Configuration Regression Testing

Any change to:

- taxonomy
- theme
- source mapping
- scoring
- prompt
- schema
- budget profile

must trigger targeted regression for affected micro-topics.

Required flow:

```text
config change
→ affected micro-topics
→ golden fixtures
→ acceptance tests
→ approve
```

## 27. Dependency-impact Testing

If a theme changes, test directly dependent micro-topics and downstream assembly where relationships exist.

Do not run every expensive test for every unrelated configuration change; keep the dependency map explicit.

## 28. P0 / P1 / P2 Production Gate

### P0 — blocking

- security
- RAG correctness
- micro-topic routing/isolation
- provenance
- temporal safety
- schema/semantic/business validation
- duplicate events
- no-update correctness
- YouTube scope restriction
- SMTP correctness
- critical integration tests

### P1 — important for strong production quality

- source diversity
- confidence calibration
- conflict detection
- genericness/usefulness detector
- performance optimization
- robust incremental evidence handling

### P2 — enhancement

- advanced semantic search
- trend visualization
- advanced analytics
- additional retrieval providers

Production gate:

> All P0 + required P1 pass. P2 is not a reason to block the V1 architecture.

## 29. Final Completion Matrix

| Area | Required state |
|---|---|
| Taxonomy | complete + tested |
| Theme engine | exact micro-topic routing |
| Source layer | configured + acceptance-tested |
| News ingestion | functional + bounded |
| YouTube | configured channels only |
| RAG | actual retrieval execution |
| Retrieval | eligibility + scoring + diversity |
| Context | bounded ContextPacket |
| AI | provider abstraction + structured output |
| Validation | schema + semantic + provenance + business |
| Event intelligence | stable IDs + dedup + incremental evidence |
| Entity intelligence | stable IDs + history |
| Opportunity detection | evidence-gated |
| Confidence | calibrated + conflict-aware |
| Newsletter | useful + non-generic + deduplicated |
| Email | SMTP + secrets protected |
| Archive | deterministic + retained |
| Testing | unit + integration + golden fixtures |
| Security | no secret leakage + injection resistance |
| Cost | micro-topic + run budgets |
| Reliability | retry/error isolation |
| Versioning | taxonomy/theme/prompt/scoring/schema/pipeline |

## 30. Final Implementation Principle

Optimize in this order:

```text
correctness
> traceability
> micro-topic accuracy
> evidence
> usefulness
> reliability
> cost
> simplicity
> extensibility
```

Do not add infrastructure merely to make the architecture appear more advanced.


## 31. Publication Delivery Tests

### Case A — delivery succeeds, archive fails

Expected:

```text
DELIVERY_CONFIRMED
→ ARCHIVE_ATTEMPTED
→ ARCHIVE_FAILED / repair-required state
```

No second email may be generated during archive repair.

### Case B — archive succeeds, delivery fails

Expected:

```text
DELIVERY_FAILED
→ archived artifact retained
→ retry delivery using the same edition identity
```

A successful archive must not be treated as proof that the newsletter was delivered.

### Case C — SMTP outcome unknown

Expected:

```text
DELIVERY_UNKNOWN
```

No blind duplicate send. Retry requires an idempotent decision using the persisted `edition_key`, delivery state, and implementation-specific SMTP evidence.

## 32. Idempotency Acceptance Test

Execute the same logical edition twice.

Expected:

```text
same edition_key
same artifact identity
0 duplicate emails
0 duplicate newsletter records
0 duplicate archive entries
0 duplicate events
0 duplicate micro-topic results
0 unnecessary AI calls on the rerun
```

This is P0.

## 33. Completeness Assertions

CI must fail when any of these are false:

```python
assert enabled_micro_topics == themed_micro_topics
assert enabled_micro_topics == budgeted_micro_topics
assert enabled_micro_topics == test_covered_micro_topics
```

Also reject orphan themes, duplicate canonical IDs, and missing theme budgets.

## 34. Retrieval Quality Benchmark

Maintain a small golden retrieval benchmark of 20–50 queries spanning important micro-topics. Each query defines expected relevant evidence.

Track at minimum:

```text
Recall@K
Precision@K
MRR or equivalent ranking score
irrelevant-context rate
duplicate-context rate
```

Set configurable pass thresholds. V1 does not require academic-scale evaluation; it requires measurable regression protection.

## 35. Unnecessary AI Call Metric

Track:

```text
ai_unnecessary_call_rate
```

Expected zero AI calls for:

- invalid source;
- duplicate content already fully processed;
- `NO_RELEVANT_CONTENT`;
- hard-ineligible RAG candidates;
- `BUDGET_SKIPPED`;
- no-context micro-topic jobs.

Exceptions must be explicit in configuration and tests.

## 36. Classification Tests

Test HIGH/MEDIUM/LOW/CONFLICTING outcomes and assert:

- MEDIUM requires positive evidence and no strong negative signal;
- LOW does not silently create a narrow micro-topic assignment;
- CONFLICTING falls back safely and emits a review flag;
- `max_micro_topics_per_content` is never exceeded without a configured exception.

## 37. Source Usage Tests

For every production-enabled source verify that its configured usage/retention status is permitted and internally consistent with the storage path and extraction method.

## 38. POST-AI Event/Entity Enrichment Naming

Use the explicit module/stage name:

```text
POST-AI EVENT/ENTITY ENRICHMENT
```

Deterministic event/entity signals remain pre-AI; post-AI logic only enriches already-established relationships and never silently replaces deterministic identity rules.
