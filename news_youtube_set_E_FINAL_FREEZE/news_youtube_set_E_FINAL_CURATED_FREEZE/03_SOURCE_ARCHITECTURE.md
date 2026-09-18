# Set E — Final Curated Specification
# 03 — Source Architecture

## 1. Source Layer Purpose

The source layer answers only:

> What configured information can the pipeline collect, normalize, and provide as evidence?

It does not decide the final intelligence narrative.

Each source record should carry:

```yaml
source_id:
name:
kind: RSS | API | HTML | OFFICIAL | YOUTUBE
trust_tier: 1 | 2 | 3 | 4
region:
country:
configured: true | false
enabled: true | false
capabilities: []
allowed_micro_topics: []
url:
collection_method:
```

## 2. Trust Tiers

Trust tier is a retrieval/ranking signal, not a factual truth label.

| Tier | Role | Typical use |
|---|---|---|
| 1 | Primary / official | original announcement, filing, regulator, ministry, company release |
| 2 | Major wire / major press | independent reported confirmation and broad coverage |
| 3 | Specialist / trade / expert | domain depth and technical interpretation |
| 4 | Aggregator / community / lead-only | discovery lead, weak evidence unless corroborated |

Evidence type still determines what the system may claim.

## 3. Recommended Source Families

The registry should be configuration-driven and verified before enablement.

### Global / major reporting

- Reuters
- Associated Press
- BBC
- Financial Times
- Bloomberg
- The Wall Street Journal

### Specialist / technology

- TechCrunch
- MIT Technology Review
- Ars Technica
- specialist semiconductor, cybersecurity, defence, space, finance, and trade publications as justified

### India / official

- Press Information Bureau
- Reserve Bank of India
- Securities and Exchange Board of India
- MeitY
- ISRO
- Ministry of Defence
- Ministry of External Affairs
- Ministry of Finance
- DPIIT
- Department of Commerce

### United States / official

- White House
- Congress
- Federal Reserve
- SEC
- NIST
- NASA
- Department of Commerce
- Department of Defense

### Europe / UK

- European Commission
- ECB
- ESA
- CERN
- UK Government
- Bank of England
- BBC / FT for independent reporting

### East Asia

- relevant China ministries and PBOC
- Xinhua / CGTN as state sources requiring contextual treatment
- METI / BOJ / JAXA
- South Korean government / MSIT
- Bank of Korea / Yonhap
- Taiwan government and semiconductor sources
- Nikkei where licensed/usable

### Middle East

- UAE government / WAM
- Saudi government / SPA / PIF
- Qatar government / QNA
- Israel government / Innovation Authority
- independent Reuters/AP/BBC/FT coverage

### Russia / Ukraine / Eurasia

- relevant official government / central-bank sources
- Ukrainian official sources
- Reuters/AP/BBC/FT and independent corroboration

### Oceania

- Australian Government
- Reserve Bank of Australia
- CSIRO
- Australian Space Agency
- ABC
- Reuters

Do not treat the existence of a source name in this document as proof that its feed/API is currently usable. Every enabled source must pass the source acceptance test.

## 4. Source Usage / Retention Policy

Each configured source record must declare, where applicable:

```yaml
usage_status: PERMITTED | RESTRICTED | DISABLED | UNKNOWN
collection_method: RSS | API | HTML | MANUAL | OTHER
license_or_terms_checked: true | false
extraction_allowed: true | false | unknown
attribution_required: true | false | unknown
full_text_storage_allowed: true | false | unknown
retention_policy: LIMITED | REQUIRED | CONFIGURED | DISABLED
```

A source is not production-enabled when its collection or storage permissions are unresolved. The registry may contain candidate sources, but only accepted sources participate in scheduled ingestion.

## 4. Source Acceptance Gate

A source becomes production-enabled only after:

```text
configured?
  ↓
reachable?
  ↓
collection method works?
  ↓
response/feed valid?
  ↓
fresh enough?
  ↓
expected fields present?
  ↓
content extractable?
  ↓
source role appropriate?
  ↓
region/topic mapping valid?
  ↓
evidence useful?
  ↓
PASS / DISABLE / QUARANTINE
```

A successful HTTP/feed response alone is insufficient.

Persist source-test results so failures are diagnosable.

## 5. News Collection

Preferred collection order is configuration-driven:

1. existing repository adapter, when suitable;
2. official API, when access exists;
3. RSS/Atom feed;
4. permitted HTML extraction;
5. source-specific fallback.

Normalized news fields should include:

```yaml
content_id:
source_id:
title:
canonical_url:
published_at:
updated_at:
retrieved_at:
author:
body_text:
content_hash:
```

`published_at`, `updated_at`, and `retrieved_at` must remain distinct.

## 6. Feedparser

Feedparser is appropriate for RSS/Atom parsing where compatible with the existing project.

Official documentation:

https://feedparser.readthedocs.io/

Do not add a second feed parser implementation without need.

## 7. Article Extraction

Reuse the repository's existing extraction logic where adequate. Trafilatura is a suitable rule-based option when the current extractor does not meet quality requirements.

Official documentation:

https://trafilatura.readthedocs.io/en/latest/usage-python.html

Extraction must be bounded to avoid pathological input sizes.

## 8. YouTube V1 Contract

Only explicitly configured channels are eligible.

Canonical route:

```text
configured channel_id
  ↓
channel upload playlist
  ↓
playlistItems.list
  ↓
videos.list
  ↓
video metadata
  ↓
transcript capability check
  ↓
transcript intelligence OR explicit metadata-only state
```

The YouTube Data API documentation confirms that a channel's uploaded videos can be retrieved via its uploads playlist and `playlistItems.list`. `playlistItems.list` currently has a 1-unit quota impact. [Official API reference](https://developers.google.com/youtube/v3/docs/playlistItems/list)

## 9. YouTube Search Rule

Global `search.list` must not be part of normal V1 channel ingestion.

A future opt-in secondary search feature, if ever added, must be separately configured and disabled by default. It must not silently turn into unrestricted discovery.

## 10. YouTube Metadata Contract

Store at minimum:

```yaml
video_id:
channel_id:
channel_name:
title:
published_at:
updated_at:
canonical_url:
duration:
description:
tags:
thumbnail_url:
content_type:
guest_if_identified:
transcript_status:
transcript_source:
transcript_text:
```

Metadata such as thumbnails and tags is auxiliary; it is not a substitute for substantive content evidence.

## 11. YouTube Transcript Capability State Machine

```text
TRANSCRIPT_AVAILABLE
  → transcript intelligence

TRANSCRIPT_UNAVAILABLE
  → explicit metadata-only / no-transcript path

TRANSCRIPT_ACCESS_ERROR
  → TRANSCRIPT_UNAVAILABLE + diagnostics

NO_PERMISSION
  → METADATA_ONLY or TRANSCRIPT_UNAVAILABLE
```

Never infer or fabricate transcript text when it was not actually obtained.

Current YouTube API caption methods have authorization and quota constraints; the implementation must verify actual access before assuming public transcript availability. See:

- https://developers.google.com/youtube/v3/docs/captions/list
- https://developers.google.com/youtube/v3/docs/captions/download

## 12. Source-to-Micro-topic Hints

Sources may provide hints such as:

```yaml
source_id: example
micro_topic_hints:
  - semiconductor.foundries
  - semiconductor.export_controls
```

Hints reduce search space but do not override the classifier when content evidence disagrees.

## 13. Collection Budgets

Each source has bounded limits such as:

```yaml
max_items_per_run:
max_pages:
max_bytes:
request_timeout_seconds:
retry_count:
```

Global and micro-topic budgets still apply downstream.

## 14. Failure Isolation

A failed source must not terminate the entire edition.

Persist:

```yaml
source_id:
run_id:
error_type:
status_code:
attempt_number:
retry_after:
backoff_seconds:
last_error:
terminal_failure:
```

## 15. Provenance

Source provenance must survive every transformation that can lead to a published claim.

At minimum:

```yaml
source_id:
source_name:
source_url:
source_type:
trust_tier:
published_at:
updated_at:
retrieved_at:
retrieval_rank:
retrieval_score:
retrieval_reason:
```

## 16. Technical References

- YouTube API overview: https://developers.google.com/youtube/v3/getting-started
- YouTube API reference: https://developers.google.com/youtube/v3/docs
- `playlistItems.list`: https://developers.google.com/youtube/v3/docs/playlistItems/list
- `videos.list`: https://developers.google.com/youtube/v3/docs/videos/list
- Captions list: https://developers.google.com/youtube/v3/docs/captions/list
- Captions download: https://developers.google.com/youtube/v3/docs/captions/download
- Feedparser: https://feedparser.readthedocs.io/
- Trafilatura: https://trafilatura.readthedocs.io/en/latest/usage-python.html
