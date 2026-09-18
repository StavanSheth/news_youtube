# Set E — Final Curated Specification
# 06 — Newsletter / Report / Email

## 1. Newsletter Identity

The newsletter is a presentation layer over validated intelligence records. It does not independently retrieve sources or call external APIs.

Required editions:

- Morning
- Night

## 2. Report Types

Retained report types:

- Executive Summary
- Top Events
- Case Studies
- Technical Deep Dives
- Executive Briefs
- Short Summaries
- Flash Updates
- Opportunities

A single edition may contain multiple report types according to configured significance.

## 3. Information Hierarchy

Canonical structure:

```text
DAILY INTELLIGENCE
  ↓
EXECUTIVE SUMMARY
  ↓
TOP EVENTS
  ↓
DOMAIN / TOPIC SECTIONS
  ↓
MICRO-TOPIC RESULTS
  ↓
CASE STUDIES / TECHNICAL DEEP DIVES when triggered
  ↓
OPPORTUNITIES
  ↓
WHAT TO WATCH
  ↓
SOURCES / EVIDENCE
```

## 4. Executive Summary

Should answer:

> What are the few developments worth knowing without reading the full edition?

Each item should be specific, evidence-backed, and non-duplicative.

Avoid generic macro commentary.

## 5. Top Events

Each top event should provide, as applicable:

- event title
- what happened
- why it matters
- what changed
- evidence/source trail
- confidence
- affected entities
- implication
- what to watch

A top event is event-centric, not article-centric.

## 6. Micro-topic Coverage

The newsletter must show meaningful coverage by micro-topic rather than implying the broad domain is fully covered because a few articles were found.

Example:

```text
AI

Foundation Models → 2 meaningful updates
AI Agents        → 1 meaningful update
RAG              → No major updates
AI Infrastructure → 3 meaningful updates
AI Safety        → Insufficient evidence
```

## 7. No-update Display

Use the exact status meaning:

- `NO_MAJOR_UPDATE` → “No major updates”
- `NO_RELEVANT_CONTENT` → “No relevant content found”
- `INSUFFICIENT_EVIDENCE` → “Evidence insufficient for a reliable update”
- `BUDGET_SKIPPED` → do not disguise as an intelligence result; render as an operational omission only when policy permits
- `TRANSCRIPT_UNAVAILABLE` → explicit video transcript limitation

Never manufacture filler merely to make every micro-topic look active.

## 8. Case Studies / Technical Deep Dives

Trigger only when significance and evidence thresholds are met.

A deep dive should add material detail, not restate a headline.

Useful fields:

- context
- mechanism/workflow
- evidence
- implementation detail
- limitations
- what is new
- practical implications

## 9. Video Intelligence Presentation

For substantive videos, present:

- source/channel
- what was said/demonstrated
- key ideas
- evidence/examples
- workflow/method
- tools
- limitations/contradictions
- source-stated action
- AI-derived experiment/application

Never imply the speaker said an AI-generated conclusion.

## 10. Actions

Label actions clearly:

```text
Source-stated
AI-derived
AI-derived experiment
Personalized application
```

Actions should be omitted when evidence does not justify them.

## 11. Opportunities

Only publish as an opportunity when supported.

Required where applicable:

- issuer
- eligibility
- deadline
- action
- application URL
- opportunity status

Do not turn a company funding article into a user opportunity without evidence.

## 12. What to Watch

“What to watch” may include:

- expected decisions
- scheduled announcements
- open risks
- unresolved conflicts
- next event milestones

It must be grounded in current evidence or explicitly labeled as a reasoned watch item.

## 13. Newsletter Budget

Newsletter budgets are separate from AI budgets.

Configure at least:

```yaml
max_total_items:
max_top_events:
max_micro_topic_findings_per_topic:
max_words_total:
max_words_per_event:
max_words_per_micro_topic:
max_sources_displayed:
```

The builder should remove lower-value content first, not randomly truncate a major finding.

## 14. Event Reuse / Deduplication

One event may support multiple sections only when each section adds new context.

Do not repeat the same prose in:

- Executive Summary
- Top Events
- Micro-topic section

Use concise references in summary sections and full analysis once.

## 15. Source Presentation

Each material claim should lead back to a source link.

Use concise source display while preserving exact URL in HTML/Markdown output where appropriate.

## 16. Evidence Language

Use language that matches evidence:

- “confirmed by” for strong direct evidence;
- “reported by” for independent reporting;
- “the source claims” when claim status matters;
- “evidence suggests” when interpretation is warranted;
- “unclear” / “conflicting reports” when unresolved.

Do not upgrade evidence language merely because the source has a high trust tier.

## 17. Quality: Usefulness Gate

Every major finding should be judged on:

| Criterion | Question |
|---|---|
| Novelty | Is this actually new/useful? |
| Relevance | Is it relevant to this micro-topic? |
| Specificity | Is it concrete rather than generic? |
| Evidence | Is support strong enough? |
| Implication | Does it explain why it matters? |
| Actionability | Is an action justified? |
| Conciseness | Can it be said more clearly? |
| Signal/noise | Would removing it improve the newsletter? |

## 18. Genericness Detector

Flag phrases and patterns that provide little intelligence unless grounded by a concrete development.

Examples of low-value defaults:

- “AI continues to evolve rapidly.”
- “Organizations should monitor developments.”
- “Businesses should consider leveraging AI.”

Combine:

```text
generic-phrase heuristic
+
specificity check
+
source-grounding check
+
action-specificity check
```

Possible outcome:

`QUALITY_REVIEW_REQUIRED`

or a bounded regeneration attempt.

## 19. “Why Should I Care?” Gate

For every major finding:

```text
What happened?
Why does it matter?
What changes because of it?
```

If “why it matters” is only a paraphrase of the summary, flag for review.

## 20. HTML Email

Generate email-safe HTML from the validated newsletter model.

The renderer must not introduce new factual claims.

Keep HTML compatible with common email clients; avoid unnecessary client-side scripting.

## 21. SMTP

Use Python's standard `smtplib` unless the existing repository already has an equivalent abstraction.

Official documentation:

https://docs.python.org/3/library/smtplib.html

SMTP credentials must come from GitHub Secrets/environment variables, never committed configuration.

## 22. Newsletter Versioning

Persist:

```yaml
edition_id:
run_id:
template_version:
newsletter_schema_version:
```

## 23. Publication State Machine

Publication is a stateful delivery workflow, not a single boolean.

```text
PREPARED
→ RENDERED
→ DELIVERY_ATTEMPTED
→ DELIVERY_CONFIRMED | DELIVERY_UNKNOWN | DELIVERY_FAILED
→ ARCHIVE_ATTEMPTED
→ ARCHIVED
```

`DELIVERY_UNKNOWN` means the SMTP operation ended without reliable confirmation of whether the message was accepted/delivered. It must never be treated as equivalent to `DELIVERY_FAILED`.

Archive failure after confirmed delivery must preserve the delivered edition identity and schedule/archive state for repair without generating another delivery. Delivery failure after successful preparation must preserve the rendered artifact for safe retry.

### SMTP ambiguity rule

An SMTP timeout or connection loss after the client has handed off a message can produce uncertain delivery. Do not blindly send the same edition again. Use the deterministic `edition_key` and persisted delivery state to make a retry decision. When delivery status cannot be proven idempotently, prefer `DELIVERY_UNKNOWN` plus operational repair over duplicate delivery.

## 24. Idempotent Publication Contract

For the same `edition_key` and logical run intent:

```text
same input
→ same edition identity
→ same newsletter artifact identity
→ no duplicate event/result/archive
→ no unnecessary AI analysis
→ no second email after confirmed delivery
```

## 25. Quality Gates

Publication must fail or be withheld when required gates fail:

- invalid schema
- broken provenance for material claims
- unsupported factual claims
- duplicate events
- severe genericness
- unresolved critical validation contradiction
- secret leakage
- malformed HTML/links

## 26. Output Principle

The finished newsletter should feel like an intelligence brief, not an article dump:

```text
specific development
→ evidence
→ why it matters
→ what changes
→ justified action/watch item
```
