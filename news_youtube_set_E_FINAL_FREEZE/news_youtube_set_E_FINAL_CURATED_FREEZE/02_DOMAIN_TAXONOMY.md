# Set E — Final Curated Specification
# 02 — Domain / Topic / Micro-topic Taxonomy

## 1. Taxonomy Purpose

The taxonomy is the classification contract used by the classifier, theme router, RAG query builder, analysis schema, and newsletter.

A broad topic is never sufficient when a configured micro-topic exists.

Canonical ID rules:

- lowercase
- stable slug
- unique within the taxonomy
- no duplicate aliases across incompatible micro-topics

## 2. Canonical Hierarchy

```text
Domain
  └── Topic
       └── Micro-topic
            └── Theme
                 └── Analysis Contract
```

A piece of content may map to multiple micro-topics only when the evidence genuinely supports each mapping. Multi-label classification must not be used to inflate coverage.

### Classification confidence

Classification produces one of four decision states:

| State | Rule | Result |
|---|---|---|
| `HIGH` | strong positive signals and no material negative signals | assign the micro-topic |
| `MEDIUM` | useful positive evidence but some ambiguity | assign only when configured positive evidence exceeds the acceptance threshold |
| `LOW` | weak or generic evidence | keep at broader topic level or `UNCLASSIFIED` |
| `CONFLICTING` | strong signals point to incompatible micro-topics | keep broader routing and emit a review flag |

Confidence thresholds are configuration-driven. Deterministic evidence takes precedence over a model's free-form confidence claim.

### Multi-label cap

Use a hard `max_micro_topics_per_content` configuration value. The default V1 policy is `2`. More than the default requires an explicit theme/taxonomy exception and must be covered by cost and regression tests.

### Coverage completeness invariant

For every enabled micro-topic, CI must prove all four mappings exist:

```text
enabled taxonomy micro-topics
= themed micro-topics
= budgeted micro-topics
= test-covered micro-topics
```

## 3. Canonical Domains and Micro-topics

### 3.1 Artificial Intelligence

- foundation models
- LLMs
- multimodal AI
- reasoning models
- AI agents
- agentic workflows
- coding models
- RAG
- embeddings
- training
- inference
- fine-tuning
- AI infrastructure
- AI tooling
- open-source AI
- enterprise AI
- AI applications
- AI research
- AI safety / alignment
- AI evaluation
- AI regulation
- AI startups

### 3.2 Software Engineering

- programming languages
- frameworks
- IDE and developer tools
- APIs
- SDKs
- backend
- frontend
- databases
- architecture
- DevOps
- CI/CD
- testing
- observability
- cloud / infrastructure
- open-source releases

### 3.3 GitHub / Open Source

- repositories
- model tooling
- agent frameworks
- MCP
- developer tools
- inference / serving
- libraries
- adoption
- high-impact projects
- releases
- maintainers

### 3.4 Quantum Computing

- hardware
- processors
- algorithms
- error correction
- networking
- cryptography
- research
- government programs
- applications

### 3.5 Space

- launches
- rockets
- spacecraft
- satellites
- missions
- Earth observation
- lunar programs
- Mars / deep space
- exploration
- commercial space
- space infrastructure
- space policy

### 3.6 Defence

- procurement
- military technology
- drones
- missiles
- air defence
- naval systems
- electronic warfare
- cyber warfare
- military AI
- defence policy
- strategic capabilities

### 3.7 Cybersecurity

- CVEs
- vulnerabilities
- exploits
- breaches
- ransomware
- malware
- threat actors
- campaigns
- identity
- cloud security
- application security
- AI security
- security tools
- national cybersecurity policy

### 3.8 Semiconductor Industry

- chip design
- fabs
- foundries
- GPUs
- CPUs
- accelerators
- memory
- HBM
- manufacturing equipment
- packaging
- process nodes
- export controls
- supply chains
- capacity

### 3.9 Startups / Venture Capital

- funding
- seed / Series rounds
- VC activity
- acquisitions
- IPOs
- accelerators
- valuation
- exits
- launches
- failures

### 3.10 Government / Policy

- regulation
- legislation
- ministries
- digital policy
- AI policy
- semiconductor policy
- industrial policy
- subsidies
- grants
- tenders
- implementation

### 3.11 Regional / Subnational Government

- state/provincial policy
- incentives
- industrial parks
- infrastructure
- local regulation
- regional investment
- regional technology policy

### 3.12 Geopolitics

- bilateral relations
- alliances
- sanctions
- wars/conflicts
- diplomacy
- trade
- technology restrictions
- strategic supply chains
- strategic competition
- regional blocs

### 3.13 Energy

- oil
- gas
- electricity
- renewables
- nuclear
- batteries
- grids
- energy companies
- energy markets
- production
- energy transition
- energy security

### 3.14 Shipping / Logistics

- ports
- shipping lines
- freight
- logistics infrastructure
- chokepoints
- maritime trade
- container rates
- disruptions
- resilience

### 3.15 Manufacturing / Industrial Policy

- factories
- industrial corridors
- incentives
- reshoring
- localization
- capacity
- exports
- industrial strategy

### 3.16 Leaders / People

- executives
- founders
- researchers
- government leaders
- appointments
- departures
- statements
- strategic decisions

### 3.17 Technology Companies

- product launches
- strategy
- acquisitions
- partnerships
- earnings
- infrastructure
- platform changes
- corporate AI / technology strategy

### 3.18 Conferences

- Google I/O
- GTC
- WWDC
- NeurIPS
- ICML
- CVPR
- major industry events
- keynotes

### 3.19 Research

- AI research
- computer science
- medicine
- economics
- physics
- climate
- engineering
- breakthroughs
- preprints
- peer-reviewed papers

### 3.20 Opportunities

- grants
- tenders
- scholarships
- fellowships
- accelerators
- hackathons
- funding programs
- government schemes
- calls for participation

### 3.21 Finance

- central banks
- interest rates
- inflation
- GDP
- employment
- equities
- bonds
- currencies
- commodities
- banking
- credit
- asset managers
- macroeconomics

## 4. Event Types

Canonical event types:

- `PRODUCT_OR_MODEL_LAUNCH`
- `RESEARCH_PUBLICATION`
- `FUNDING`
- `ACQUISITION`
- `PARTNERSHIP`
- `REGULATION`
- `GOVERNMENT_SCHEME`
- `SECURITY_INCIDENT`
- `INFRASTRUCTURE_DEVELOPMENT`
- `MARKET_DEVELOPMENT`
- `TRADE_DEVELOPMENT`
- `LEADERSHIP_CHANGE`
- `CONFERENCE_ANNOUNCEMENT`
- `POLICY_ANNOUNCEMENT`
- `CONFLICT_DEVELOPMENT`
- `EARNINGS_OR_RESULT`
- `FACILITY_OR_FACTORY_ANNOUNCEMENT`
- `CONTRACT_OR_PROCUREMENT_AWARD`

## 5. Entity Types

- person
- company
- organization
- government
- country
- region/city
- technology
- product
- model
- framework
- research paper
- institution
- laboratory
- university
- financial instrument
- infrastructure asset
- conference

Stable entity IDs should be deterministic from canonical name/type plus disambiguating information where required.

## 6. Content Types

### News

- news report
- official release
- regulatory filing/notice
- research/report
- analysis/commentary
- interview
- announcement

### Video

- podcast
- interview
- case study
- tutorial
- explainer
- product/demo
- news report
- commentary
- lecture/talk
- conference
- documentary

## 7. Region Model

Canonical regions:

- India / South Asia
- North America
- Europe / EU
- UK
- Middle East
- East Asia — China/Japan/South Korea/Taiwan
- Southeast Asia
- Russia / Eurasia
- Ukraine
- Oceania
- Africa
- Latin America
- Global

Region is metadata, not a substitute for topic classification.

## 8. Classification Rules

1. Match title, description, extracted body/transcript, source metadata, entities, and aliases where available.
2. Prefer the narrowest supported micro-topic.
3. Use multiple micro-topics only when evidence supports each.
4. Prefer explicit configured aliases over fuzzy guessing.
5. Do not infer a micro-topic from source reputation alone.
6. Borderline cases may remain broader rather than being forced into a wrong micro-topic.
7. Classification is deterministic-first; AI classification may be used only as a bounded fallback when configured.

## 9. Micro-topic Record Contract

```yaml
micro_topic_id:
domain_id:
topic_id:
display_name:
aliases: []
keywords: []
negative_keywords: []
priority: P0 | P1 | P2 | P3
theme_id:
stream_contract:
  news: {}
  video: {}
budget_profile: {}
source_hints: []
version:
```

## 10. Micro-theme Contract

Each micro-topic must define:

- detection signals
- negative signals where ambiguity is known
- required evidence fields
- questions the analysis must answer
- significance rules
- entity/event expectations
- opportunity triggers where relevant
- stream-specific requirements
- output sections
- action rules
- no-update behavior

Example: the RAG micro-topic focuses on retrieval architecture, chunking, embeddings, ranking/reranking, context selection, evaluation, architecture tradeoffs, operational behavior, and practical workflow implications—not generic AI commentary.

## 11. No-update States

```text
NO_RELEVANT_CONTENT
  = nothing relevant was found/accepted.

NO_MAJOR_UPDATE
  = relevant content existed and was evaluated, but nothing passed the publication threshold.

INSUFFICIENT_EVIDENCE
  = potentially relevant material existed, but evidence quality/conflict prevented a publishable conclusion.

BUDGET_SKIPPED
  = job was not fully executed due to explicit budget policy.
```

These statuses must remain distinct in storage and newsletter rendering.

## 12. Taxonomy Versioning

Persist:

```yaml
taxonomy_version:
theme_version:
prompt_version:
scoring_version:
schema_version:
pipeline_version:
```

A taxonomy/configuration change triggers targeted regression tests for affected micro-topics and dependent newsletter assembly.
