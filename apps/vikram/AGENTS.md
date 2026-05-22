# Vikram Agent Guide

## Scope

This file applies to `apps/vikram/`.

Vikram is deprecated as a platform app. Do not add it back to shared Compose,
Caddy, CI, production deploy workflows, or root helper scripts unless the user
explicitly asks to reintroduce it.

## Project Shape

- `vikram/agent.py`: builds the Google ADK agent and runnable wrapper.
- `vikram/api.py`: FastAPI routes for `/chat`, threaded messages, DBOS events, Telegram, and health.
- `vikram/gateway.py`: SQLite `ThreadStore`, threaded conversation service, and CloudEvent helpers.
- `vikram/dbos_gateway.py`: DBOS queues and workflows.
- `vikram/telegram.py`: Telegram webhook parsing, allowlist, commands, and replies.
- `vikram/tools.py`: `TOOL_REGISTRY`; specs reference these names.
- `spec/vikram/`: default agent spec and prompt.

## Commands

- `uv sync --project apps/vikram --locked`
- `uv run --project apps/vikram --locked pytest apps/vikram/tests -q`
- `uv run --project apps/vikram vikram`
- `uv run --project apps/vikram vikram-api`

## Configuration

Use `VIKRAM_*` variables for app-specific settings. Vikram uses Google ADK with
Gemini by default, configured through `VIKRAM_MODEL` and `GOOGLE_API_KEY`.

Keep tests offline by default. Gate live model calls behind `VIKRAM_RUN_EVALS=1`.
