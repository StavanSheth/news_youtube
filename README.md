# YouTube + News Intelligence System

A personal, GitHub Actions-driven intelligence pipeline. It discovers configured YouTube and RSS sources, deduplicates them using repository files, classifies them against configurable topics, uses Gemini for structured analysis, publishes Markdown and email-safe HTML reports, sends email, and commits the new state back to GitHub.

## Architecture

The application is Python under `src/intelligence`. Only explicitly enabled YouTube channel IDs are collected in production; global topic search is disabled by default and exists only as an explicit configuration opt-in. RSS ingestion is a small adapter layer so new source types can be added without changing orchestration. Persistent data is JSON under `data/`; reports are versioned under `output/`. No database or running service is used.

The runtime builds a taxonomy-backed micro-topic catalog, groups likely events, retrieves bounded local evidence per micro-topic, and then sends only that evidence to the intelligence manager. Gemini receives a stream-aware profile: news emphasizes confirmed change and implications, while video/podcast content emphasizes arguments, methods, tools, workflows, and experiments. Reports separate **Source facts** from **AI interpretation** and **Actionable insights**, and show micro-topic coverage plus source health.

## Setup

1. Configure `config/channels.yaml`, setting actual YouTube channel IDs and `enabled: true`.
2. Configure RSS feeds, source families, topic definitions, entity aliases, prompts, scoring weights, and limits in `config/settings.yaml`, `config/source_registry.yaml`, `config/topics.yaml`, `config/entities.yaml`, and `config/prompts.yaml`.
3. In GitHub repository settings, add the required Actions secrets below.
4. Enable Actions and use **Run workflow** once to verify delivery.

Install locally with `pip install -r requirements.txt`. Run `pytest` to test. A local dry run, which avoids Gemini and email, is `python src/main.py --dry-run`. A deterministic end-to-end fixture run is `python src/main.py --dry-run --fixture tests/fixture_corpus.json`.

## Required secrets

`YOUTUBE_API_KEY` and `GEMINI_API_KEY` are required for the full scheduled pipeline. Email delivery requires `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_FROM`, and `EMAIL_TO`. Use `.env.example` only as a reference; do not commit real values.

Create a YouTube Data API key in Google Cloud with YouTube Data API v3 enabled. Create a Gemini key in Google AI Studio or Google Cloud. Restrict both keys appropriately. The workflow never prints secret values.

## Scheduling and output

`.github/workflows/intelligence.yml` runs at 07:30, 13:30, and 19:30 Asia/Kolkata (02:00, 08:00, 14:00 UTC). GitHub Actions cron uses UTC, hence the translated expressions. It also supports manual dispatch.

Every run writes `output/<edition_key>/<run_id>/digest.md` and `digest.html`, where the logical edition key is `YYYY-MM-DD|EDITION|TIMEZONE` and the filesystem folder uses a safe equivalent. The HTML is a purpose-built responsive newsletter template in `templates/newsletter.html`, not a Markdown conversion. The generated HTML is the email body and both report files are attached. Runtime version contracts and run state are persisted under `data/`.

Each run also writes `quality.json` and `source_validation.json`. SMTP delivery is attempted only when the deterministic quality gate passes; source failures are recorded separately from `NO_MAJOR_UPDATE` coverage.

## State and retries

`processed_videos.json` and `processed_news.json` prevent successful items from being processed again. `failed_items.json` records the error, attempt count, and retry time; a failed item is deliberately not marked processed. `processing_state.json` retains reports and recent structured analyses. `entities.json`, `events.json`, and `trends.json` retain compact cross-run intelligence links, `delivery_state.json` records SMTP success/failure without secrets, and each report also writes `quality.json` with deterministic output checks. No database is required.

## Operations

The Action tests before processing, runs the pipeline, then stages only `data` and `output`. Its `contents: write` permission is the minimum needed to push state. Concurrency serialization and a rebase before push reduce collisions with manual repository edits. Generated commits do not recursively trigger the schedule because the workflow only uses `schedule` and `workflow_dispatch`.

For quota control, favor channels over broad search, set a small `max_keyword_results_per_topic`, and use `max_items_per_run`. Global YouTube search is disabled by default; the configured channel registry is authoritative. Missing transcripts and individual feed/API/AI errors are isolated per item; processing continues and errors are kept for retry. Check `failed_items.json`, `source_validation.json`, and the latest `quality.json` first when troubleshooting. The deterministic acceptance command is `python src/main.py --dry-run --fixture tests/fixture_corpus.json`.
