# Phase 3: Production Source & API Readiness Specification

## 1. Executive Overview

Phase 3 establishes a deterministic, production-grade source ingestion, validation, and health management architecture for the `news_youtube` intelligence pipeline against the frozen Set-E requirements (`03_SOURCE_ARCHITECTURE.md`, `07_ARCHITECTURE_REQUIREMENTS.md`, `08_IMPLEMENTATION_RULES.md`).

Prior to Phase 3, source definitions in `config/source_registry.yaml` and `config/channels.yaml` were passive configurations without runtime verification, lifecycle state enforcement, or quota safety bounds. Phase 3 transforms the source layer into an active, deterministic source acceptance lifecycle:
```text
CONFIGURED
  ↓
REACHABLE
  ↓
AUTHENTICATED
  ↓
COLLECTION WORKS
  ↓
RESPONSE VALID
  ↓
FRESH ENOUGH
  ↓
REQUIRED FIELDS PRESENT
  ↓
CONTENT EXTRACTABLE
  ↓
SOURCE ROLE VALID
  ↓
REGION/TOPIC MAPPING VALID
  ↓
EVIDENCE QUALITY VALID
  ↓
LICENSE/TERMS METADATA VALID
  ↓
HEALTH RECORDED
  ↓
PASS (READY) / DISABLE / QUARANTINE
```

Only sources achieving **READY** status enter production retrieval and RAG. Failing sources are partitioned into **DISABLED** or **QUARANTINED** with actionable diagnostic error codes, preventing corrupt, stale, or malformed data from polluting downstream intelligence generation without consuming Gemini API tokens.

---

## 2. Source Acceptance Lifecycle & State Machine

### 2.1 Acceptance Pipeline Gates
The `SourceAcceptanceEngine` (`src/intelligence/source_validation.py`) executes 13 sequential verification gates:

| Step | Gate Name | Validation Criteria | Failure Status & State |
|:---|:---|:---|:---|
| 1 | `CONFIGURED` | Required configuration fields (`id`, `name`, `type`, `role`, `trust_tier`, `domains`, `topics`) are present and schema-valid. | `QUARANTINE` / `SCHEMA_INVALID` |
| 2 | `REACHABLE` | Endpoint host is resolvable and returns valid HTTP status within timeout limits (<15s). | `QUARANTINE` / `REACHABILITY_FAILED` |
| 3 | `AUTHENTICATED` | If `authentication_required=true`, verify required API key or credentials exist in environment. | `QUARANTINE` / `AUTHENTICATION_REQUIRED` |
| 4 | `COLLECTION_WORKS` | Fetch sample payload; verify network connection, non-empty response body, bounded payload size. | `QUARANTINE` / `COLLECTION_FAILED` |
| 5 | `RESPONSE_VALID` | Parser (XML/RSS, JSON, YouTube API) parses content without unhandled bozo exceptions or malformed structures. | `QUARANTINE` / `INVALID_RESPONSE` |
| 6 | `FRESH_ENOUGH` | Most recent item timestamp falls within `max_age_hours` (default 48h) or `stale_after_hours` (default 72h). | `QUARANTINE` / `STALE` |
| 7 | `REQUIRED_FIELDS_PRESENT` | Canonical item fields (`title`, `url`, `published_at`, `content_hash`) must be extractable. | `QUARANTINE` / `SCHEMA_INVALID` |
| 8 | `CONTENT_EXTRACTABLE` | Item contains non-empty text (body text, summary, or transcript) above minimum threshold (>50 chars). | `QUARANTINE` / `CONTENT_UNAVAILABLE` |
| 9 | `SOURCE_ROLE_VALID` | Source role belongs to canonical `SourceRole` enum and matches domain capabilities. | `QUARANTINE` / `ROLE_INVALID` |
| 10 | `REGION_TOPIC_MAPPING_VALID` | Declared domains and topics match canonical `config/taxonomy.yaml`. | `QUARANTINE` / `MAPPING_INVALID` |
| 11 | `EVIDENCE_QUALITY_VALID` | Trust tier (1–4) and evidence type are defined and adhere to institutional standards. | `QUARANTINE` / `EVIDENCE_INSUFFICIENT` |
| 12 | `LICENSE_TERMS_METADATA_VALID` | License status, attribution requirement, and storage permission are explicitly defined. | `QUARANTINE` / `SCHEMA_INVALID` |
| 13 | `HEALTH_RECORDED` | Health record is atomically persisted to `data/source_health/<source_id>.json`. | Status recorded: `READY`, `DISABLED`, or `QUARANTINED` |

### 2.2 Lifecycle States & Status Codes
- **SourceLifecycleState** (`src/intelligence/sources.py`):
  `REGISTERED`, `CONFIGURED`, `AUTHENTICATION_REQUIRED`, `AUTHENTICATED`, `REACHABILITY_FAILED`, `COLLECTION_FAILED`, `INVALID_RESPONSE`, `STALE`, `SCHEMA_INVALID`, `CONTENT_UNAVAILABLE`, `ROLE_INVALID`, `MAPPING_INVALID`, `EVIDENCE_INSUFFICIENT`, `QUARANTINED`, `DISABLED`, `READY`.
- **SourceAcceptanceStatus**:
  - `READY` (`PASS`): Source cleared all 13 gates; fully eligible for production ingestion.
  - `DISABLED` (`DISABLE`): Source explicitly turned off via configuration (`enabled: false`); bypassed cleanly.
  - `QUARANTINED` (`QUARANTINE`): Source failed one or more verification gates; strictly blocked from production retrieval.

---

## 3. Canonical Domain Contracts & Data Model

### 3.1 Source Roles (`SourceRole`)
The system recognizes 9 canonical source roles:
1. `NEWS`: General and specialized news agencies (e.g., Reuters, BBC, TechCrunch).
2. `VIDEO`: Video broadcast and analysis channels (e.g., YouTube channels).
3. `RESEARCH`: Academic papers, preprint archives, and research institutions (e.g., arXiv, Nature).
4. `OFFICIAL`: Official standards bodies and international organizations (e.g., NIST, CERN, ESA).
5. `GOVERNMENT`: Executive and regulatory government publications (e.g., White House, European Commission).
6. `COMPANY`: Corporate announcements, engineering blogs, and investor relations (e.g., OpenAI, Google).
7. `GITHUB`: Software releases, repositories, and technical changelogs.
8. `MARKET`: Financial exchanges, market data feeds, and central bank communications.
9. `SPECIALIST`: Domain-specific publications, newsletters, and focused industry outlets.

### 3.2 Canonical Content Contract (`CanonicalContent`)
Ingestion adapters normalize raw payloads into the unified `CanonicalContent` dataclass (`src/intelligence/ingestion/base.py`):

```python
@dataclass
class CanonicalContent:
    content_id: str                      # SHA-256 deterministic identifier
    source_id: str                       # Registered source identifier
    source_type: str                     # "rss", "youtube", "news_api"
    source_role: SourceRole              # Canonical source role
    title: str                           # Sanitized title
    canonical_url: str                   # Cleaned, normalized URL
    published_at: str                    # ISO 8601 UTC timestamp
    updated_at: str                      # ISO 8601 UTC timestamp
    retrieved_at: str                    # ISO 8601 UTC timestamp
    author: str                          # Item author or channel title
    body_text: str                       # Clean extracted text
    summary_text: str                    # Item summary or description
    content_hash: str                    # SHA-256 of normalized body/summary
    evidence_type: str                   # "article", "transcript", "document"
    trust_tier: int                      # Tier 1 (authoritative) to Tier 4 (unverified)
    region: str                          # Geographic region
    country: str                         # ISO country code or "GLOBAL"
    domains: list[str]                   # Taxonomy domain mapping
    topics: list[str]                    # Taxonomy topic mapping
    micro_topics: list[str]              # Microtopic IDs covered
    metadata: dict[str, Any]             # Adapter-specific provenance metadata
```

### 3.3 Policies & Budgets
- **FreshnessPolicy**: Defines `max_age_hours` (default 48), `stale_after_hours` (default 72), and `schedule` ("daily", "hourly").
- **CollectionBudget**: Enforces `max_items_per_run` (default 25), `max_pages` (default 1), `max_bytes` (default 5MB), `timeout_seconds` (default 15), and `retry_count` (default 2).

---

## 4. Modular Ingestion Adapters

The ingestion layer (`src/intelligence/ingestion/`) is organized into dedicated provider modules, maintaining full backward compatibility with legacy consumers (`enriched_rss`, `article_text`, `clean_html`):

### 4.1 Safe HTTP Client (`SafeHttpClient`)
Shared resilient HTTP client (`src/intelligence/ingestion/base.py`):
- **Bounded Payload Sizes**: Hard enforcement of `max_bytes` (5MB default) to prevent memory exhaustion from oversized feeds.
- **Categorized Retries**: Retryable status codes (408, 429, 500, 502, 503, 504) with exponential backoff; non-retryable client errors (400, 401, 403, 404) fail fast without wasted attempts.
- **Credential Masking**: Strips and masks `key=`, `api_key=`, `token=`, and Bearer tokens from request logs and error messages.

### 4.2 RSS / Feed Ingestion Suite (`src/intelligence/ingestion/rss/`)
- `client.py`: Safe feed retrieval with configurable timeouts and custom user agent (`NewsYoutubeIntelligence/3.0`).
- `parser.py`: Feedparser wrapper with bozo error classification (`URLError`, `HTTPError`, `SAXParseException`, `BozoError`).
- `normalizer.py`: Extracts distinct UTC timestamps (`published_at`, `updated_at`, `retrieved_at`), computes SHA-256 content hashes, and extracts clean full-text via readability heuristics.

### 4.3 YouTube Suite & Quota Guard (`src/intelligence/ingestion/youtube/`)
- `quota.py` (`YouTubeQuotaTracker`):
  - Tracks unit costs: Search (100 units), List (1 unit), Videos (1 unit), Channels (1 unit).
  - Enforces daily budget limit (default 10,000 units).
  - **Circuit Breaker**: On HTTP 403 `quotaExceeded`, trips immediately to block subsequent YouTube calls during the run.
- `client.py` (`YouTubeClient`):
  - Adheres strictly to channel-targeted ingestion: Channel ID -> Uploads Playlist -> Playlist Items -> Video Details.
  - Zero unconstrained global searches in V1, minimizing quota burn.
- `transcripts.py` (`YouTubeTranscriptManager`):
  - Deterministic 5-state transcript lifecycle:
    - `TRANSCRIPT_AVAILABLE`: Transcript downloaded and parsed.
    - `TRANSCRIPT_UNAVAILABLE`: Video does not provide captions.
    - `TRANSCRIPT_FAILED`: Network or parsing error during retrieval.
    - `TRANSCRIPT_EMPTY`: Caption track exists but contains 0 text lines.
    - `TRANSCRIPT_NOT_ALLOWED`: Disabled by channel permissions.
- `normalizer.py` (`YouTubeNormalizer`):
  - Assembles video metadata and caption text into canonical `CanonicalContent` records.

### 4.4 News API Suite (`src/intelligence/ingestion/news_api/`)
- `client.py` (`NewsApiClient`):
  - Paginated JSON retrieval with strict rate-limit backoff on HTTP 429.
  - Passes API key via `X-Api-Key` header; logs zero secrets.
- `normalizer.py` (`NewsApiNormalizer`):
  - Maps provider articles into canonical contracts with provenance retention.

---

## 5. Deduplication, Failure Isolation & Provenance

### 5.1 Multi-Key Deduplication
Deduplication combines three orthogonal keys:
1. Normalized Canonical URL (`https://...` stripped of tracking query params like `utm_*`).
2. Provider Item ID (e.g. YouTube Video ID, RSS `<guid>`).
3. SHA-256 Content Hash (`hashlib.sha256(normalized_text.encode()).hexdigest()`).

Items matching an existing URL or content hash within the run are skipped, preventing duplicate stories from multiple RSS mirrors.

### 5.2 Failure Isolation
Ingestion operates under strict failure isolation:
- A failure in an individual source (e.g., DNS resolution failure, HTTP 500, expired SSL cert, malformed XML) is trapped and isolated.
- The failing source is marked with a detailed diagnostic record in `data/source_health/<source_id>.json`.
- The pipeline continues executing across all healthy sources.
- The edition run status is downgraded to `DEGRADED` but does not abort, ensuring unbroken delivery.

### 5.3 Complete Provenance Chain
Every item entering RAG retains an immutable provenance trace:
```text
source_id → provider_item_id → content_id → evidence_id → canonical_url → published_at_utc
```
ContextPackets generated for Gemini prompts include this provenance header, enabling factual citations and attribution without hallucinated origins.

---

## 6. Micro-Topic Coverage Analysis

Cross-referencing the 49 configured production sources against the 236 canonical micro-topic records in `config/microtopic_matrix.json`:

### 6.1 Domain & Topic Reach
- **Total Canonical Matrix Records**: 236 micro-topics
- **Unique Micro-topic IDs**: 226 distinct identifiers
- **Covered Domains**: 14 of 14 domains (100% domain representation)
  - `artificial-intelligence`, `cybersecurity`, `defence`, `finance`, `geopolitics`, `government-policy`, `manufacturing`, `quantum-computing`, `research`, `semiconductors`, `software-engineering`, `space`, `startups-vc`, `technology-companies`.
- **Covered Topics**: 43 major topics (including `ai-policy`, `macroeconomics`, `chip-design`, `bilateral-relations`, `foundation-models`, `space-policy`).
- **Direct Micro-topic Mappings**: 33 specific micro-topic anchors explicitly mapped in source configuration, with broader domain/topic rules catching remaining items.

### 6.2 Source Role Distribution
- `NEWS`: 28 sources (Reuters, BBC, TechCrunch, Ars Technica, MIT Tech Review, etc.)
- `GOVERNMENT` / `OFFICIAL`: 14 sources (White House, DoD, European Commission, ECB, Bank of Japan, etc.)
- `RESEARCH`: 3 sources (CERN, ESA, CSIRO)
- `VIDEO`: 4 authoritative YouTube channels

---

## 7. Observability & Operations

### 7.1 Source Validation CLI
The `intelligence.source_validation` module provides a comprehensive CLI for operational diagnostics:
```bash
# Validate all sources (offline/structural validation)
python -m intelligence.source_validation --all

# Output structured JSON report
python -m intelligence.source_validation --all --json

# Validate specific source
python -m intelligence.source_validation --source reuters

# Run live network reachability and collection checks (opt-in)
python -m intelligence.source_validation --all --live

# Fail on error (for CI pipelines)
python -m intelligence.source_validation --all --fail-on-error
```

### 7.2 Metrics Telemetry (`MetricsRegistry`)
Source-level telemetry counters:
- `source_checks_total`: Total validation checks executed.
- `sources_ready_total`: Sources verified as `READY`.
- `sources_quarantined_total`: Sources failing verification.
- `youtube_requests_total`: Total YouTube API calls.
- `youtube_quota_units_used`: Quota units consumed.
- Stage duration timers: `stage_2_collecting_ms`, `stage_5_deduping_ms`.

### 7.3 Health Probes
`src/intelligence/observability/health.py` exposes `check_source_health(repository)` to aggregate persistent health states across all sources for system dashboards.
