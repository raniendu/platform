# Deployment

Raman now deploys as an app inside the platform monorepo. The source lives in
`apps/raman/`; GitHub Actions builds it into
`ghcr.io/raniendu/platform/raman:<sha>` when `DEPLOY_RAMAN=true`.

For a snapshot of the system being containerized, see
[current_architecture.md](current_architecture.md). Platform-level routing,
secrets, and production runbooks live under the root `docs/` directory.

## Image

| Property | Value |
|---|---|
| Registry | `ghcr.io/raniendu/platform/raman` |
| Base | `ghcr.io/astral-sh/uv:python3.13-trixie` (Debian 13; SQLite 3.46+ avoids DBOS first-run migration issues seen on older SQLite) |
| Workdir | `/app` |
| User | root (matches current platform image conventions) |
| Port | `8000` (plain HTTP) |
| Healthcheck | `GET /healthz` |
| Persistent state | `/app/.raman` |
| Entrypoint | `uvicorn raman.api:app --host 0.0.0.0 --port 8000` |

The Dockerfile copies only runtime code and agent specs into the image. Tests,
evals, docs, local state, and secret env files are excluded by `.dockerignore`.

## Environment

All variables flow through `raman.settings.RamanSettings`.

Required for production:

| Variable | Notes |
|---|---|
| `RAMAN_MODEL_PROVIDER` | Production uses `digitalocean`; local defaults to `ollama`. |
| `RAMAN_DEV_MODEL` | Provider-specific model identifier. Production currently uses `gemma-4-31B-it`. |
| `DO_INFERENCE_API_KEY` | Required when `RAMAN_MODEL_PROVIDER=digitalocean`. |

Required for Telegram:

| Variable | Notes |
|---|---|
| `TELEGRAM_BOT_TOKEN` | From BotFather for the default `spec/telegram.toml` bot. |
| `TELEGRAM_WEBHOOK_SECRET` | Random string echoed in `X-Telegram-Bot-Api-Secret-Token`; generate with `openssl rand -hex 32`. |
| `TELEGRAM_ALLOWED_CHAT_IDS` | Comma-separated chat IDs allowed to use the default bot. |
| `TELEGRAM_BOT_USERNAME` | Bot username without `@`; required for group mentions and reply-to-bot detection. |
| `GOBIND_TELEGRAM_BOT_TOKEN` | From BotFather for the checked-in Gobind bot. |
| `GOBIND_TELEGRAM_WEBHOOK_SECRET` | Random string echoed in `X-Telegram-Bot-Api-Secret-Token` for Gobind. |
| `GOBIND_TELEGRAM_ALLOWED_CHAT_IDS` | Comma-separated chat IDs allowed to use Gobind. |
| `GOBIND_TELEGRAM_BOT_USERNAME` | Gobind bot username without `@`; required for group mentions and reply-to-bot detection. |
| `RAMAN_PUBLIC_BASE_URL` | Public HTTPS base URL, currently `https://raman.raniendu.dev`. |

Additional Raman Telegram bots are declared in `spec/telegram.toml`; their
`token_env`, `webhook_secret_env`, and `allowed_chat_ids_env` names must be
present in the local env file or production Raman env file.

Optional:

| Variable | Default | Notes |
|---|---|---|
| `PARALLEL_API_KEY` | unset | Required by the current `spec/raman` because it enables `web_search`. |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Used only with the Ollama provider. |
| `DO_INFERENCE_BASE_URL` | `https://inference.do-ai.run/v1` | Override only if DigitalOcean changes its endpoint. |
| `RAMAN_DB_PATH` | `/app/.raman/raman.sqlite3` in the image | Volume-mount the parent directory. |
| `DBOS_SYSTEM_DATABASE_URL` | `sqlite:///app/.raman/dbos.sqlite3` | Override to use another DBOS state store. |
| `RAMAN_AGENT` | `raman` | Default agent spec to load on startup. |
| `RAMAN_LOG_LEVEL` | `INFO` | Structured JSON log level for stdout logs. |
| `RAMAN_OBSERVABILITY_ENABLED` | `false` | Enable OpenLIT/OpenTelemetry tracing. |
| `RAMAN_OTLP_ENDPOINT` | unset | OTLP endpoint. Use `http://jaeger:4318` with the Compose Jaeger service. |
| `RAMAN_OBSERVABILITY_CAPTURE_MESSAGE_CONTENT` | `false` | Capture prompt/reply content in traces. Forced off in production. |
| `RAMAN_OBSERVABILITY_DISABLED_INSTRUMENTORS` | `mistral` | Comma-separated OpenLIT instrumentors to skip. |

## Runtime State

Mount one persistent volume at `/app/.raman`. It holds `raman.sqlite3` for
thread history and Telegram dedupe state plus `dbos.sqlite3` for DBOS workflow
state. Losing this volume loses conversation history and in-flight workflow
state, but not the app code or agent specs.

## Runtime Logs

Raman logs to stdout as structured JSON. There is no app-managed log file. In
local Compose, read logs with:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local logs -f raman
```

In production, the logs are the Raman container stdout on the Droplet. Inspect
them with the production Compose project over SSH. The logs intentionally use
hashed chat/thread IDs and lengths instead of raw prompt text, replies, tokens,
or webhook secrets.

## Runtime Traces

Raman can initialize OpenLIT and export OpenTelemetry traces when
`RAMAN_OBSERVABILITY_ENABLED=true`. Local Compose includes a pinned Jaeger v2
all-in-one service:

```bash
RAMAN_OBSERVABILITY_ENABLED=true docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build raman jaeger
open http://localhost:16686
```

Production Compose includes Jaeger behind the `observability` profile. When
`DEPLOY_OBSERVABILITY=true`, the deploy workflow enables Raman tracing and sets
`RAMAN_OTLP_ENDPOINT=http://jaeger:4318` for production. The Jaeger UI is exposed
at `https://jaeger.raniendu.dev` behind Caddy basic auth using the Prefect basic
auth credentials. Add the `jaeger` DNS A record before deploying this route.

## Local Compose

The root local Compose file builds this directory and reads root `.env.local`.
The Raman service also passes `.env.local` into the container so any additional
Telegram env names referenced by `spec/telegram.toml` are available at runtime:

```bash
cp .env.example .env.local
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build raman
curl http://localhost:8000/healthz
curl http://localhost:8000/chat --json '{"prompt":"say pong"}'
```

In root `.env.local`, use `OLLAMA_BASE_URL=http://host.docker.internal:11434/v1`
so the Raman container can reach the host Ollama daemon.

For direct app development, run from `apps/raman/` and use app-local `.env`:

```bash
cd apps/raman
cp .env.example .env
uv sync --locked
uv run pytest tests -q
uv run raman-api
```

In `apps/raman/.env`, use `OLLAMA_BASE_URL=http://localhost:11434/v1` because
the process runs directly on your Mac.

To debug locally against the production DigitalOcean inference endpoint instead
of Ollama, run from the platform repo root:

```bash
./apps/raman/scripts/run-local-prod-debug.sh
```

This reads root `.env.local`, requires `DO_INFERENCE_API_KEY`, defaults to
`RAMAN_DEV_MODEL=gemma-4-31B-it`, and stores separate debug state under
`apps/raman/.raman/prod-debug/`. Pair it with ngrok and
`./apps/raman/scripts/set-local-telegram-webhook.sh https://<ngrok-host>` for
live Telegram testing.

For an app-only smoke test, this directory still includes
[`compose.example.yml`](../compose.example.yml), which pairs Raman with Ollama:

```bash
docker compose -f apps/raman/compose.example.yml up -d ollama
docker compose -f apps/raman/compose.example.yml exec ollama ollama pull qwen3
RAMAN_DEV_MODEL=qwen3 docker compose -f apps/raman/compose.example.yml up --build raman
curl http://localhost:8000/healthz
```

## Production

Production Compose uses `${RAMAN_IMAGE}` and mounts the `raman-state` Docker
volume. Caddy routes `https://raman.raniendu.dev` to `raman:8000`.

The deploy workflow appends Raman production constants and GitHub environment
secrets into `/opt/platform/.env.production` at deploy time. Do not duplicate
Raman secrets in tracked files.

## Validation

```bash
uv run --project apps/raman pytest apps/raman/tests -q
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local config
RAMAN_IMAGE=ghcr.io/raniendu/platform/raman:ci COMPOSE_PROFILES=dotdev,prefect,raman docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.example config
```

Live model calls and evals stay opt-in. Run them only with the relevant provider
or Ollama credentials configured.
