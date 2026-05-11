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
| `RAMAN_DEV_MODEL` | Provider-specific model identifier. Production currently uses `openai-gpt-oss-120b`. |
| `DO_INFERENCE_API_KEY` | Required when `RAMAN_MODEL_PROVIDER=digitalocean`. |

Required for Telegram:

| Variable | Notes |
|---|---|
| `TELEGRAM_BOT_TOKEN` | From BotFather. |
| `TELEGRAM_WEBHOOK_SECRET` | Random string echoed in `X-Telegram-Bot-Api-Secret-Token`; generate with `openssl rand -hex 32`. |
| `TELEGRAM_ALLOWED_CHAT_IDS` | Comma-separated chat IDs allowed to use the bot. |
| `RAMAN_PUBLIC_BASE_URL` | Public HTTPS base URL, currently `https://raman.raniendu.dev`. |

Optional:

| Variable | Default | Notes |
|---|---|---|
| `PARALLEL_API_KEY` | unset | Required only when the active spec enables `web_search`. |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Used only with the Ollama provider. |
| `DO_INFERENCE_BASE_URL` | `https://inference.do-ai.run/v1` | Override only if DigitalOcean changes its endpoint. |
| `RAMAN_DB_PATH` | `/app/.raman/raman.sqlite3` in the image | Volume-mount the parent directory. |
| `DBOS_SYSTEM_DATABASE_URL` | `sqlite:///app/.raman/dbos.sqlite3` | Override to use another DBOS state store. |
| `RAMAN_AGENT` | `raman` | Default agent spec to load on startup. |

## Runtime State

Mount one persistent volume at `/app/.raman`. It holds `raman.sqlite3` for
thread history and Telegram dedupe state plus `dbos.sqlite3` for DBOS workflow
state. Losing this volume loses conversation history and in-flight workflow
state, but not the app code or agent specs.

## Local Compose

The root local Compose file builds this directory and reads root `.env.local`:

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
