# Implementation Audit

## Current Reality

The repository is a Python 3.11 GitHub Actions application using JSON, YAML, Markdown, and HTML files as its only persistent storage. There is no database, frontend, service process, Telegram integration, or external archive service.

The current execution path is `src/main.py` -> `intelligence.production.run`. The production layer loads YAML, reads JSON state, collects RSS and configured YouTube content, filters and ranks items, calls Gemini for structured topic analysis, renders Markdown/HTML, optionally sends SMTP, and writes compact state. The older `intelligence.pipeline` remains as compatibility code but is no longer the CLI entry point.

## Repository Structure

- `src/intelligence/`: configuration, models, state, collectors, ingestion, classification, Gemini integration, rendering, SMTP, and orchestration.
- `config/`: channels, topics, prompts, and runtime settings.
- `data/`: processed item records, run history, and failures.
- `output/YYYY/MM/DD/HHMM/`: generated reports.
- `templates/`: legacy newsletter template retained for compatibility.
- `tests/`: unit tests for configuration, classification, state, rendering, production scoring, and schema normalization.
- `.github/workflows/intelligence.yml`: three UTC schedules, manual dispatch, tests, processing, and commit/push.

## Existing Components

YouTube uses the Data API channel uploads playlist as its primary path and has a bounded keyword search fallback. RSS uses feedparser. `ingestion.py` now adds article-page extraction and explicit transcript statuses while preserving the existing collectors. Gemini uses the Google GenAI client and a configuration-selected model. SMTP delivery already existed in `emailer.py` and is reused. State is JSON-only and GitHub Actions has `contents: write`.

## Current Tests and Validation

The repository currently has eight passing tests covering configuration, multi-topic matching, schema normalization, compact state/retry behavior, relevance, rendering, and legacy state compatibility. The local dry run generates both report formats without sending mail.

## Known Bugs and Gaps

The historical implementation had a hard-coded Gemini model, silent transcript failures, title/keyword-only RSS content, single-topic deep analysis, oversized repeated analyses in state, and no true event/entity/theme layer. The current Set C pass has started addressing those through `production.py`, `ingestion.py`, and `schema.py`, but the remaining work is to add the canonical taxonomy/theme registry, structured evidence/entities/events/opportunities/trends, real cross-source synthesis, richer newsletter sections, and source configuration migration.

The current committed channel registry is still a placeholder and must remain disabled until the owner configures explicit channels. The current default RSS entry is retained for compatibility but should be replaced with verified enabled sources. GitHub Actions has not been run successfully because repository secrets and SMTP credentials are external setup.

## Compatibility Notes

Existing processed JSON is read defensively. New writes use compact records and preserve stable item IDs. Generated local validation state and reports are intentionally not part of the production code commit.

## Recommended Minimal Path

1. Add the Set C taxonomy and theme registry as YAML configuration.
2. Extend normalized content and analysis records with optional event, entity, evidence, importance, confidence, report, trend, and opportunity fields.
3. Add deterministic event grouping, corroboration, and lightweight trend/entity persistence.
4. Route each matched theme through its configured questions and output schema.
5. Render a single structured newsletter model into improved Markdown and HTML.
6. Expand mocked tests and update README/workflow documentation.

