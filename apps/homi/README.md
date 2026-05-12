# homi

A personal CLI + HTTP agent built on the Amazon Strands SDK.

Homi is a sibling of Raman with the same platform surface: FastAPI, DBOS
threaded runs, SQLite state, Telegram webhook support, and a `web_search` tool.

## Stack

- Python 3.13+
- Strands Agents SDK with Amazon Bedrock by default
- FastAPI + uvicorn for the HTTP surface
- DBOS queues for threaded message processing
- SQLite for thread metadata and Strands message history
- uv for dependency and virtualenv management

## Setup

Run these commands from the platform root:

```bash
uv sync --project apps/homi --locked
cp apps/homi/.env.example apps/homi/.env
```

For live model calls, configure AWS credentials through standard `AWS_*`
environment variables or `AWS_BEARER_TOKEN_BEDROCK`, then set:

```env
HOMI_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0
HOMI_AWS_REGION=us-west-2
```

## Local Commands

```bash
uv run --project apps/homi homi
uv run --project apps/homi homi-api
uv run --project apps/homi pytest apps/homi/tests -q
```

The API listens on `http://127.0.0.1:8000` when run directly:

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/chat --json '{"prompt":"say pong"}'
```

With platform Compose:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build homi caddy
curl http://homi.localhost/healthz
```

## API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/healthz` | Liveness check |
| `POST` | `/chat` | Stateless single-shot agent run |
| `POST` | `/threads/{interface}/{thread}/messages` | Enqueue persistent threaded run |
| `GET` | `/events/{workflow_id}` | Inspect a DBOS workflow result |
| `POST` | `/telegram/webhook` | Telegram webhook endpoint |

Threaded runs store Strands `agent.messages` JSON in `.homi/homi.sqlite3`.
Telegram `/reset` clears that stored history for the chat.

## Configuration

Use `apps/homi/.env.example` for direct app runs and root `.env.local` for
Compose runs. Homi-specific variables use the `HOMI_*` prefix. Telegram
configuration is per app:

```env
HOMI_TELEGRAM_BOT_TOKEN=
HOMI_TELEGRAM_WEBHOOK_SECRET=
HOMI_TELEGRAM_ALLOWED_CHAT_IDS=
```

`HOMI_PARALLEL_API_KEY` enables the `web_search` tool. If it is unset, the app
falls back to `PARALLEL_API_KEY`.
