# Set E — Final Curated Specification
# 07 — Architecture Requirements

## 1. Deployment Architecture

The system runs as one repository-native Python application scheduled by GitHub Actions.

```text
                 GITHUB ACTIONS
                       │
                       ▼
              PYTHON ORCHESTRATOR
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
     NEWS COLLECTORS          YOUTUBE COLLECTOR
          └────────────┬────────────┘
                       ▼
                 NORMALIZER
                       ▼
                CHEAP FILTERS
                       ▼
              CONTENT DEDUPLICATION
                       ▼
                  CLASSIFIER
                       ▼
          ENTITY/EVENT DETERMINISTIC SIGNALS
                       ▼
                 EVENT GROUPING
                       ▼
                 THEME ROUTER
                       ▼
              MICRO-TOPIC MANAGER
                       ▼
                  RAG MANAGER
                       ▼
                  CONTEXT PACKET
                       ▼
                  AI PROVIDER
                       ▼
               SCHEMA VALIDATOR
                       ▼
              SEMANTIC VALIDATOR
                       ▼
           PROVENANCE / BUSINESS RULES
                       ▼
              EVENT/ENTITY ENRICHMENT
                       ▼
                TOPIC SYNTHESIS
                       ▼
              NEWSLETTER ASSEMBLER
                       ▼
                 MD + HTML
                       ▼
                      SMTP
                       ▼
                  GIT ARCHIVE
```

## 2. Repository-native Persistence

Use existing repository conventions, with logical separation such as:

```text
data/
  raw/
  normalized/
  rag/
  events/
  entities/
  state/
  runs/
output/
  markdown/
  html/
archive/
  newsletters/
  runs/
```

Exact directories should be reconciled with the existing repository rather than blindly duplicated.

## 3. Retention Policy

Use different retention classes:

```text
raw source material → temporary/limited
normalized records → required retention
micro-topic results → persistent
entities/events → persistent
newsletter → persistent
run metadata → persistent
```

Retention must prevent uncontrolled repository growth while preserving reproducibility.

Default configurable policy for V1:

| Data class | Default retention |
|---|---|
| Raw source material | 14 days unless required for reproducibility or legal policy |
| Normalized content | 180 days |
| Micro-topic results | Persistent |
| Events/entities | Persistent, compact records |
| Newsletters | Persistent |
| Run metadata | Persistent, compact |

Retention values are configuration, not hard-coded assumptions.

## 4. RAG Architecture Contract

```python
class RAGManager(Protocol):
    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        ...
```

The result must contain enough information to reconstruct why each context item was selected.

## 5. RAG Context Record

```yaml
content_id:
source_id:
event_id:
topic:
micro_topic:
published_at:
updated_at:
retrieved_at:
context_type:
retrieval_rank:
retrieval_score:
retrieval_reason:
evidence_type:
excerpt:
```

## 6. Micro-topic Execution

For `N` enabled/eligible micro-topics:

```text
N isolated jobs
→ N theme resolutions
→ N retrieval contexts
→ N bounded AI analyses
→ N validations
→ N result records
```

Sequential execution is acceptable for V1. Parallelism is an optimization, not a requirement.

## 7. Micro-topic Scheduling Policy

1. determine candidate/eligible micro-topics;
2. assign priorities using static configuration plus cheap activity signals;
3. resolve budgets;
4. run P0 before P1/P2/P3 as required by budget pressure;
5. record local failures;
6. record skipped work explicitly;
7. produce final run accounting.

## 8. Budget Enforcement

Budget must be enforced at the smallest relevant layer:

```text
source budget
→ retrieval budget
→ context budget
→ AI-call budget
→ output-token budget
→ total-token budget
→ run budget
```

A child budget may never override a parent hard ceiling.

## 9. AI Provider Abstraction

The provider abstraction isolates model-specific transport/configuration.

Recommended shape:

```python
class AIProvider(Protocol):
    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        ...
```

Provider configuration belongs in configuration, not scattered hard-coded constants.

## 10. Validator Architecture

```text
raw structured model output
        ↓
JSON/schema validation
        ↓
semantic validation
        ↓
provenance validation
        ↓
business-rule validation
        ↓
quality/usefulness validation
        ↓
validated micro-topic result
```

## 11. State Architecture

State must remain compact and operational.

### Processed item

```yaml
content_id:
content_hash:
processed_at:
last_status:
source_id:
```

Do not unnecessarily duplicate entire analysis payloads in operational state.

### Failed item

```yaml
content_id:
run_id:
error_type:
attempt_number:
retry_after:
backoff_seconds:
last_error:
terminal_failure:
```

### Micro-topic result

```yaml
micro_topic_result_id:
run_id:
edition:
micro_topic_id:
theme_id:
status:
importance_score:
confidence_score:
findings: []
provenance_refs: []
budget_usage: {}
quality_flags: []
```

### Event

```yaml
event_id:
status:
first_seen:
last_seen:
entity_ids: []
source_ids: []
micro_topic_ids: []
importance:
confidence:
versions: []
```

## 12. Deterministic IDs

Use stable IDs/hashes where useful:

- `content_hash`
- `event_id`
- `entity_id`
- `micro_topic_result_id`
- `newsletter_item_id`
- `edition_id`
- `run_id`

This supports reruns, deduplication, and archive integrity.

## 13. Canonical Edition and Publication Identity

```yaml
edition_key: "YYYY-MM-DD|MORNING|Asia/Kolkata"
edition_id:
run_id:
edition_timezone:
publication_cutoff_local:
publication_cutoff_utc:
```

`edition_key` is the hard uniqueness key for a scheduled publication. Concurrency controls reduce races; the key itself prevents duplicate logical editions.

## 14. Publication Lifecycle

```text
PREPARED
→ RENDERED
→ DELIVERY_ATTEMPTED
→ DELIVERY_CONFIRMED | DELIVERY_UNKNOWN | DELIVERY_FAILED
→ ARCHIVE_ATTEMPTED
→ ARCHIVED
→ RUN_COMPLETED
```

Delivery and archival are independently recorded. A run is not retroactively marked successful merely because one side succeeded.

## 15. Operational Observability

V1 requires compact operational accounting and GitHub Actions visibility. At minimum record/flag:

- missing MORNING/NIGHT edition;
- all-source failure;
- AI failure rate above configured threshold;
- newsletter validation failure;
- SMTP failure or `DELIVERY_UNKNOWN`;
- archive failure;
- P0 micro-topic skipped unexpectedly;
- budget exhaustion.

No Prometheus/Grafana/third-party observability stack is required.

## 16. Run Lifecycle

```text
RUN_CREATED
→ CONFIG_RESOLVED
→ SOURCES_COLLECTING
→ NORMALIZED
→ CLASSIFIED
→ MICRO_TOPIC_JOBS
→ SYNTHESIS
→ NEWSLETTER_RENDERED
→ EMAIL_SENT
→ ARCHIVED
→ RUN_COMPLETED
```

Terminal outcomes may include partial/degraded states when individual sources or micro-topics fail, provided the run accurately records them.

## 17. GitHub Actions

GitHub Actions is the scheduler/orchestrator.

Use least-privilege workflow permissions. Only `contents: write` is required for repository archival when the workflow must commit output.

Official workflow syntax:

https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax

Official GITHUB_TOKEN guidance:

https://docs.github.com/en/actions/concepts/security/github_token

Timezone-aware schedules can be defined with IANA timezone information in supported GitHub Actions schedule syntax. Do not hard-code UTC assumptions into edition semantics.

## 18. Concurrency / Git Conflict Policy

Only one publication/archive writer should finalize a given edition run at a time.

When Git conflicts occur:

1. fetch latest branch;
2. rebase/pull as configured;
3. re-apply only generated artifacts safely;
4. retry bounded times;
5. fail loudly if unresolved.

Never overwrite unrelated commits.

## 19. Security Architecture

Secrets include:

- Gemini/API credentials
- YouTube credentials if required
- SMTP credentials
- any other private integration secret

Rules:

- GitHub Secrets/environment variables only;
- never log secret values;
- redact credentials from exceptions;
- source content is untrusted data;
- retrieved historical content is also untrusted data;
- prompt injection cannot alter system instructions, schema, or publication rules.

## 20. Cost Architecture

Cost controls apply at four levels:

```text
collection
→ retrieval
→ AI analysis
→ newsletter generation
```

Do cheap filtering before expensive model calls.

Avoid duplicate AI calls caused by retries, duplicate events, duplicate content, or overlapping module ownership.

## 21. Extensibility

Future capabilities should fit existing interfaces:

```text
SourceAdapter
Classifier
ThemeRouter
RAGManager
AIProvider
Validator
NewsletterRenderer
DeliveryProvider
```

New providers should not require replacing the orchestration contract.
