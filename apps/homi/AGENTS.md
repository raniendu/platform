# Homi Agent Guide

## Scope

This file applies to `apps/homi/`.

## Project Shape

- `homi/agent.py`: builds the Strands agent and runnable wrapper.
- `homi/api.py`: FastAPI routes for `/chat`, threaded messages, DBOS events, Telegram, and health.
- `homi/gateway.py`: SQLite `ThreadStore`, threaded conversation service, and CloudEvent helpers.
- `homi/dbos_gateway.py`: DBOS queues and workflows.
- `homi/telegram.py`: Telegram webhook parsing, allowlist, commands, and replies.
- `homi/tools.py`: `TOOL_REGISTRY`; specs reference these names.
- `spec/homi/`: default agent spec and prompt.

## Commands

- `uv sync --project apps/homi --locked`
- `uv run --project apps/homi --locked pytest apps/homi/tests -q`
- `uv run --project apps/homi homi`
- `uv run --project apps/homi homi-api`

## Configuration

Use `HOMI_*` variables for app-specific settings. Homi uses Strands with
Amazon Bedrock by default, configured through `HOMI_MODEL_ID`,
`HOMI_AWS_REGION`, and standard AWS credential variables.

Keep tests offline by default. Gate live model calls behind `HOMI_RUN_EVALS=1`.
