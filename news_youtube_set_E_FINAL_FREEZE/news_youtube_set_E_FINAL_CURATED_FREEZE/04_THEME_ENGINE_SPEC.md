# Set E — Final Curated Specification
# 04 — Micro-theme Engine

## 1. Purpose

The theme engine converts an exact micro-topic into the analysis contract used by RAG query construction, AI input, validation, and newsletter rendering.

The central rule is:

> Same topic does not mean same theme. Same theme may apply across News and Video, but stream-specific instructions must differ.

## 2. Theme Resolution Order

Theme resolution is deterministic:

```text
exact micro-topic theme
  ↓
exact topic-level theme
  ↓
domain-level fallback
  ↓
global fallback
```

A broader fallback must never silently override an exact configured micro-topic theme.

## 3. Theme Record

```yaml
theme_id:
domain_id:
topic_id:
micro_topic_id:
priority:
version:
detection:
  positive_signals: []
  negative_signals: []
questions: []
evidence_requirements: []
significance_rules: []
entity_fields: []
event_fields: []
stream_rules:
  news: {}
  video: {}
action_rules: {}
output_sections: []
no_update_policy: {}
```

## 4. Theme Quality Rule

Every enabled micro-topic must have an actionable theme that tells the system:

1. what evidence counts;
2. what questions to answer;
3. what constitutes significance;
4. which event/entity fields matter;
5. which output fields are mandatory;
6. what actions may be suggested;
7. how to represent no-update states.

A generic prompt such as “analyze this source for the topic” is insufficient.

## 5. Machine-Checkable Theme Completeness

A configured theme is valid only when all required fields are present and non-empty:

```text
theme_id != null
micro_topic_id != null
version != null
questions >= 1
evidence_requirements >= 1
significance_rules >= 1
stream_rules.news != null
stream_rules.video != null
no_update_policy != null
```

CI must reject an enabled micro-topic whose theme fails this contract.

## 6. Trend Detection Minimum Evidence

A trend is not inferred from volume alone. A configured trend rule must specify at least:

```yaml
minimum_distinct_dates:
minimum_distinct_sources:
minimum_evidence_items:
minimum_significance:
continuity_window_days:
```

A trend result is publishable only when all configured minimums are satisfied.

## 7. Stream-Specific Interpretation

### News

The theme should prioritize:

- new events
- changes from prior state
- official vs reported vs claimed distinctions
- corroboration
- affected entities
- practical/strategic implications
- what to watch

### Video

The theme should prioritize:

- what was actually said/demonstrated
- ideas and arguments
- evidence/examples
- workflows and methods
- tools used
- assumptions
- predictions
- limitations
- contradictions
- experiments
- practical application

## 8. Evidence Rules

For each material finding:

```text
claim
→ supporting evidence
→ source
```

Material claims without evidence fail validation.

Interpretation should be grounded in source evidence.

Inference must be explicitly marked.

## 9. Importance Rules

Importance is a bounded score, e.g. 0–100.

The score should be based on configurable deterministic and model-assisted features such as:

- magnitude of change
- affected entities
- strategic relevance
- novelty
- likely persistence
- market/operational impact
- corroboration
- user-configured priority

The model may propose a score, but business thresholds and hard caps remain deterministic.

## 10. Foundation Models Example Contract

Questions may include:

- What model or model family changed?
- What capability changed?
- What architecture or training detail is relevant?
- Which benchmarks/evidence are actually cited?
- What limitations remain?
- Is the improvement material or incremental?
- What practical workflows become possible or cheaper?

Do not turn every AI product announcement into a “foundation model” finding without model-level evidence.

## 11. AI Agents Example Contract

Questions may include:

- What agent architecture or orchestration changed?
- Which tools/actions are available?
- What autonomy level is demonstrated?
- Is the evidence a benchmark, demo, production deployment, or opinion?
- What workflow does it materially improve?
- What failure modes or control limits are present?

## 12. RAG Example Contract

The RAG micro-topic should specifically evaluate:

- retrieval architecture
- query construction
- chunking strategy
- embeddings
- reranking
- hybrid retrieval
- context selection/compression
- evaluation methods
- latency/cost tradeoffs
- grounding/provenance
- production architecture
- demonstrated workflows

Generic “AI knowledge retrieval” commentary is insufficient.

## 13. Finance / Central-bank-Type Example

Questions may include:

- What policy or macro variable changed?
- Is the source primary, reported, or analytical?
- What data or statement supports the change?
- What changed relative to the prior policy/state?
- What markets/entities are directly affected?
- What is the plausible implication versus confirmed outcome?

## 14. Case Study / Deep-Dive Triggers

A theme may request deeper treatment when:

- importance exceeds threshold;
- the source includes unusually concrete implementation detail;
- a material strategic decision occurred;
- a technical result changes practice;
- independent evidence provides a useful comparison;
- the same event gains meaningful incremental evidence.

## 15. Trend Detection

Trend detection is a synthesis capability, not a synonym for “several similar articles.”

Require repeated evidence over time, entity/topic continuity, and configurable significance.

## 16. Action Attribution

Every action carries one of:

```text
SOURCE_STATED
AI_DERIVED
AI_DERIVED_EXPERIMENT
PERSONALIZED_APPLICATION
```

If the source does not recommend an action, do not write the action as though it did.

## 17. No-update Rules

A micro-topic can report:

- `NO_MAJOR_UPDATE` after genuine evaluation;
- `NO_RELEVANT_CONTENT` when accepted evidence is absent;
- `INSUFFICIENT_EVIDENCE` when evidence cannot support a conclusion;
- `BUDGET_SKIPPED` when execution was not completed.

No generic filler may be generated to make an empty section look complete.

## 18. Theme Versioning

Persist `theme_version` with every micro-topic result.

Changing a theme requires targeted regression tests for the micro-topic and dependent newsletter assembly.
