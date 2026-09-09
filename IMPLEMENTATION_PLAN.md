# Set C Implementation Plan

## Scope

Extend the existing Python, Gemini, YouTube, RSS, JSON-state, SMTP, newsletter, and GitHub Actions stack. Do not add databases, services, frontend code, queues, or a second delivery system.

## Files To Create

- `config/taxonomy.yaml` for domains, topics, micro-topics, regions, event types, and report types.
- `config/themes.yaml` for theme detection, evidence rules, analysis questions, actions, routines, and triggers.
- `src/intelligence/newsletter.py` for the structured newsletter model shared by Markdown and HTML renderers.
- `src/intelligence/events.py` for deterministic event grouping, corroboration, entities, trends, and change signals.
- Focused tests for taxonomy/theme selection, grouping, evidence, opportunity/trend output, and newsletter sections.

## Files To Modify

- `config/topics.yaml`: migrate to Set C-compatible keys and thresholds while keeping existing topic names readable.
- `config/settings.yaml`: source, Gemini, state, scoring, newsletter, and archive limits.
- `src/intelligence/models.py`: add optional content, evidence, event, entity, theme, report, and opportunity fields.
- `src/intelligence/production.py`: execute source -> filter -> dedupe -> group -> classify -> theme -> intelligence -> newsletter stages.
- `src/intelligence/ingestion.py` and `src/intelligence/sources.py`: preserve source isolation, lookback, explicit transcript status, and configured-channel-only YouTube behavior.
- `src/intelligence/schema.py` and Gemini provider: validate Set C output fields and retry malformed/transient responses.
- `templates/newsletter.html` or the new newsletter renderer: executive brief, events, topic sections, actions, opportunities, trends, and sources.
- `README.md`, tests, and workflow documentation.

## Dependencies

Prefer the standard library and existing dependencies. Do not add infrastructure dependencies. The existing Google GenAI, feedparser, requests, YAML, transcript, pytest, and Ruff dependencies remain.

## Compatibility and Migration

Read old processed records by ID, ignore unknown legacy fields, and write compact records going forward. Do not delete historical state. New optional fields remain nullable. Existing `src/intelligence/pipeline.py` and legacy renderer remain available until the new path is covered by tests.

## Testing Gates

- After taxonomy/theme changes: config, multi-topic, threshold, and theme precedence tests.
- After event/entity changes: URL/hash/title grouping, corroboration, change, trend, and opportunity tests.
- After newsletter changes: structured-model, Markdown, HTML, no-empty-section, links, and routine labeling tests.
- Final: pytest, Ruff, dry run, output inspection, idempotent rerun, failure isolation, workflow YAML review, and secret-log review.

## Risks

- Free Gemini quotas can limit a large run; filter and cap before AI.
- Source pages can change markup; RSS summary remains the fallback.
- Existing state may contain older verbose records; migration must be bounded and non-destructive.
- GitHub Actions commit races require the existing concurrency group and rebase/push sequence.

## Deferred Set A Features

Source-health dashboards, AI cost accounting, reviewer agents, search indexes, queues, advanced event versioning, trend graphs, semantic search, and analytics remain deferred. The data model will retain extension points without implementing those systems.

