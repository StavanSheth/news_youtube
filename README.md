# YouTube + News Intelligence System

A personal, GitHub Actions-driven intelligence pipeline. It discovers configured YouTube and RSS sources, deduplicates them using repository files, classifies them against configurable topics, uses Gemini for structured analysis, publishes Markdown and email-safe HTML reports, sends email, and commits the new state back to GitHub.

## Architecture

The application is Python under `src/intelligence`. YouTube channel uploads are the primary discovery path; bounded keyword searches are secondary. RSS ingestion is a small adapter layer (`discover_rss`) so new source types can be added without changing orchestration. Persistent data is JSON under `data/`; reports are versioned under `output/`. No database or running service is used.

Gemini receives bounded chunks, first producing source-grounded extraction and then topic-specific analysis. The reports visibly separate **Source facts** from **AI interpretation** and **Actionable insights**. A routine is retained only when the model returns a substantiated one.

## Setup

1. Configure `config/channels.yaml`, setting actual YouTube channel IDs and `enabled: true`.
2. Configure RSS feeds, topic definitions, prompts, scoring weights, and limits in `config/settings.yaml`, `config/topics.yaml`, and `config/prompts.yaml`.
3. In GitHub repository settings, add the required Actions secrets below.
4. Enable Actions and use **Run workflow** once to verify delivery.

Install locally with `pip install -r requirements.txt`. Run `pytest` to test. A local dry run, which avoids Gemini and email, is `python src/main.py --dry-run`.

## Required secrets

`YOUTUBE_API_KEY` and `GEMINI_API_KEY` are required for the full scheduled pipeline. Email delivery requires `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_FROM`, and `EMAIL_TO`. Use `.env.example` only as a reference; do not commit real values.

Create a YouTube Data API key in Google Cloud with YouTube Data API v3 enabled. Create a Gemini key in Google AI Studio or Google Cloud. Restrict both keys appropriately. The workflow never prints secret values.

## Scheduling and output

`.github/workflows/intelligence.yml` runs at 07:30, 13:30, and 19:30 Asia/Kolkata (02:00, 08:00, 14:00 UTC). GitHub Actions cron uses UTC, hence the translated expressions. It also supports manual dispatch.

Every run writes `output/YYYY/MM/DD/HHMM/digest.md` and `digest.html`. The HTML is a purpose-built responsive newsletter template in `templates/newsletter.html`, not a Markdown conversion. The generated HTML is the email body and both report files are attached.

## State and retries

`processed_videos.json` and `processed_news.json` prevent successful items from being processed again. `failed_items.json` records the error, attempt count, and retry time; a failed item is deliberately not marked processed. `processing_state.json` retains reports and recent structured analyses, allowing future change detection and cross-source synthesis extensions without a database.

## Operations

The Action tests before processing, runs the pipeline, then stages only `data` and `output`. Its `contents: write` permission is the minimum needed to push state. Concurrency serialization and a rebase before push reduce collisions with manual repository edits. Generated commits do not recursively trigger the schedule because the workflow only uses `schedule` and `workflow_dispatch`.

For quota control, favor channels over broad search, set a small `max_keyword_results_per_topic`, and use `max_items_per_run`. Missing transcripts and individual feed/API/AI errors are isolated per item; processing continues and errors are kept for retry. Check `failed_items.json` first when troubleshooting.
