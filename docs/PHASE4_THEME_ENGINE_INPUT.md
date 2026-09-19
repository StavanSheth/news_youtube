# Phase 4 Theme Engine Handoff Specification

## 1. Scope & Objective

This document defines the canonical interface contract, data models, and architectural invariants for transferring normalized content from the **Phase 3 Source Ingestion Layer** into the **Phase 4 Theme & Story Intelligence Engine**.

Phase 3 guarantees that every item arriving at the Phase 4 boundary has passed the 13-stage source acceptance lifecycle, is fully normalized into `CanonicalContent`, has been deduplicated across multiple keys, and contains an unbroken provenance chain.

---

## 2. Ingestion Boundary Guarantees

Before any item reaches Stage 6 (Theme Classification), the Phase 3 pipeline guarantees:

1. **Deterministic Acceptance**: The item's origin source has achieved `READY` (`PASS`) status in `ProductionSourceRegistry`. No items from `DISABLED` or `QUARANTINED` sources are present.
2. **Freshness Invariant**: The item publication timestamp (`published_at`) satisfies:
   $$\text{lookback\_floor} \le \text{published\_at} \le \text{edition\_cutoff}$$
   Stale items (>48h or >72h depending on policy) and future-dated items (>cutoff) are eliminated.
3. **Multi-Key Deduplication**:
   - Normalized Canonical URL is unique within the edition.
   - SHA-256 Content Hash is unique within the edition.
   - Provider item ID is unique within the source.
4. **Structural Validity**:
   - `title`: Non-empty, sanitized text string (HTML stripped, entities decoded).
   - `body_text` / `summary_text`: Non-empty content exceeding minimum length thresholds (>50 chars).
   - `content_id`: Deterministic SHA-256 digest (`src/intelligence/identity.py`).
   - `retrieved_at`: Explicit ISO 8601 UTC timestamp distinct from publication time.

---

## 3. Canonical Input Contract (`CanonicalContent`)

Phase 4 consumes items formatted as `CanonicalContent` records or their dictionary representations:

```python
{
    "content_id": "c7a8b9f0e1d2c3b4a5f6e7d8c9b0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8",
    "source_id": "reuters",
    "source_type": "rss",                         # "rss" | "youtube" | "news_api"
    "source_role": "NEWS",                        # NEWS, VIDEO, RESEARCH, OFFICIAL, GOVERNMENT, etc.
    "title": "Global Semiconductor Alliance Announces Advanced Packaging Standard",
    "canonical_url": "https://www.reuters.com/technology/packaging-standard-2026",
    "published_at": "2026-09-19T08:30:00Z",
    "updated_at": "2026-09-19T08:45:00Z",
    "retrieved_at": "2026-09-19T09:00:00Z",
    "author": "Jane Doe",
    "body_text": "Full extracted article or video transcript text...",
    "summary_text": "Semiconductor alliance members agree on next-generation packaging specs.",
    "content_hash": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
    "evidence_type": "article",                  # "article" | "transcript" | "document"
    "trust_tier": 1,                             # 1 (Authoritative) to 4 (Unverified)
    "region": "GLOBAL",
    "country": "GLOBAL",
    "domains": ["semiconductors", "technology-companies"],
    "topics": ["chip-design", "supply-chains"],
    "micro_topics": ["advanced-packaging", "interconnect-standards"],
    "metadata": {
        "article_status": "EXTRACTED",
        "fetch_latency_ms": 142.5,
        "transcript_status": "NOT_APPLICABLE"
    }
}
```

---

## 4. Taxonomy & Micro-Topic Routing

Each `CanonicalContent` record carries pre-classified taxonomy hints derived from source contracts:

### 4.1 Domains & Topics Hierarchy
- `domains`: Top-level taxonomy categories from `config/taxonomy.yaml` (e.g., `semiconductors`, `artificial-intelligence`, `geopolitics`, `finance`).
- `topics`: Mid-level topic classifications within the domain (e.g., `chip-design`, `foundation-models`, `macroeconomics`).
- `micro_topics`: Specific micro-topic nodes mapped to the 236 canonical records in `config/microtopic_matrix.json`.

### 4.2 Routing Responsibilities for Phase 4
1. **Validation**: Validate that incoming domain/topic tags exist within `config/taxonomy.yaml`.
2. **Expansion**: When a story touches multiple domains (e.g., US Export Controls on AI Chips touching `geopolitics`, `semiconductors`, and `artificial-intelligence`), route the item to all applicable candidate themes.
3. **Weighting by Trust Tier**: Apply trust-tier weights during cluster ranking:
   - **Tier 1 (Authoritative/Official)**: Weight 1.0 (Primary anchor sources)
   - **Tier 2 (Major Press/Corporate)**: Weight 0.8
   - **Tier 3 (Specialist Publications)**: Weight 0.6
   - **Tier 4 (Community/General)**: Weight 0.4

---

## 5. Provenance & Attribution Invariants

Phase 4 clustering and theme synthesis must strictly preserve item provenance:

1. **No Anonymous Citations**: Every synthesized theme and cluster must retain the explicit list of backing `content_id`s.
2. **Context Packet Preservation**: When preparing RAG context for Gemini structured generation, the item's canonical URL, source ID, and publication date must remain bound to the extracted evidence text:
   ```text
   [SOURCE: reuters | ID: c7a8b9f0 | PUBLISHED: 2026-09-19T08:30:00Z]
   Global Semiconductor Alliance Announces Advanced Packaging Standard...
   ```
3. **Audit Trail**: Phase 4 Theme manifests (`theme_manifest.json`) must link every story cluster back to the ingested `content_id`s stored in `data/normalized/`.
