# vikram

Deprecated: Vikram is no longer part of the platform's shared Compose, Caddy,
CI, or production deploy paths. This app directory is retained only as archived
code for direct local reference.

A personal CLI + HTTP agent built on Google ADK.

Vikram is a sibling of Raman with the same platform surface: FastAPI, DBOS
threaded runs, SQLite state, Telegram webhook support, and a `web_search` tool.

## Stack

- Python 3.13+
- Google ADK with Gemini by default
- FastAPI + uvicorn for the HTTP surface
- DBOS queues for threaded message processing
- SQLite for thread metadata, DBOS state, and ADK `DatabaseSessionService`
- uv for dependency and virtualenv management

## Setup

Run these commands from the platform root:

```bash
uv sync --project apps/vikram --locked
cp apps/vikram/.env.example apps/vikram/.env
```

For live model calls, configure:

```env
GOOGLE_API_KEY=
VIKRAM_MODEL=gemini-flash-latest
```

## Local Commands

```bash
uv run --project apps/vikram vikram
uv run --project apps/vikram vikram-api
uv run --project apps/vikram pytest apps/vikram/tests -q
```

The API listens on `http://127.0.0.1:8000` when run directly:

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/chat --json '{"prompt":"say pong"}'
```

## API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/healthz` | Liveness check |
| `POST` | `/chat` | Stateless single-shot agent run |
| `POST` | `/threads/{interface}/{thread}/messages` | Enqueue persistent threaded run |
| `GET` | `/events/{workflow_id}` | Inspect a DBOS workflow result |
| `POST` | `/telegram/webhook` | Telegram webhook endpoint |

Threaded runs store an ADK session reference in `.vikram/vikram.sqlite3`; ADK
conversation events live in `.vikram/adk_sessions.sqlite3`. Telegram `/reset`
clears the active session reference so the next chat starts a fresh ADK session.

## Configuration

Use `apps/vikram/.env.example` for direct app runs. Vikram-specific variables
use the `VIKRAM_*` prefix. Telegram configuration is per app:

```env
VIKRAM_TELEGRAM_BOT_TOKEN=
VIKRAM_TELEGRAM_WEBHOOK_SECRET=
VIKRAM_TELEGRAM_ALLOWED_CHAT_IDS=
```

`VIKRAM_PARALLEL_API_KEY` enables the `web_search` tool. If it is unset, the
app falls back to `PARALLEL_API_KEY`.
