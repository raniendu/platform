# Local Development

## Prerequisites

- Docker Desktop with Compose v2.
- `uv` installed locally.
- Ports `80`, `3100`, `4200`, `8000`, `8001`, `8002`, `8080`, and `8501` available.

## Environment

Create local environment values from the example file:

```bash
cp .env.example .env.local
```

Keep `.env.local` untracked. Empty API keys are acceptable for local container startup; flows that call Gemini or Pushover need real values before execution. Paperclip can also pass through `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `GEMINI_API_KEY` when you want provider-backed agent features locally. Raman local Compose builds `apps/raman` and defaults to a host Ollama server at `http://host.docker.internal:11434/v1`. Homi and Vikram need AWS or Google credentials only for live `/chat` calls.

The example file includes local Paperclip Caddy credentials with user `admin` and password `paperclip_local`. Change them in `.env.local` if needed.

Raman, Homi, and Vikram have separate app-level env files for direct `uv` runs:

```bash
cp apps/raman/.env.example apps/raman/.env
cp apps/homi/.env.example apps/homi/.env
cp apps/vikram/.env.example apps/vikram/.env
```

Do not make root `.env.local` and `apps/raman/.env` identical by default. The
root file is for Docker Compose and includes all platform apps. The app file is
only for running Raman from `apps/raman/`. The main value that differs is
`OLLAMA_BASE_URL`:

```env
# root .env.local, used by the Raman container
OLLAMA_BASE_URL=http://host.docker.internal:11434/v1

# apps/raman/.env, used by direct uv runs on your Mac
OLLAMA_BASE_URL=http://localhost:11434/v1
```

## Python Environments

Each app keeps its own `pyproject.toml`, `uv.lock`, and virtual environment. This avoids forcing the Flask site, Prefect flows, and Airflow image into one shared Python resolution.

```bash
uv sync --project apps/dotdev
uv sync --project apps/raman
uv sync --project apps/homi
uv sync --project apps/vikram
uv sync --project apps/prefect
uv sync --project apps/flow
```

The root helper runs all app environment syncs:

```bash
./scripts/sync-apps.sh
```

The helper forwards normal `uv sync` flags, so this checks lockfile consistency without updating locks:

```bash
./scripts/sync-apps.sh --locked
```

If you run the helper while a different app venv is activated, `uv` may warn
that `VIRTUAL_ENV` does not match the target project. That is harmless; `uv`
ignores the active venv and uses each app's own `.venv`. To silence it:

```bash
deactivate
./scripts/sync-apps.sh --locked
```

## Tests

```bash
uv run --project apps/dotdev pytest apps/dotdev/tests -q
uv run --project apps/raman pytest apps/raman/tests -q
uv run --project apps/homi pytest apps/homi/tests -q
uv run --project apps/vikram pytest apps/vikram/tests -q
uv run --project apps/prefect pytest apps/prefect/tests/property/
uv run --project apps/flow python apps/flow/scripts/validate-dags.py
uv run --project apps/flow pytest apps/flow/tests/
```

The root helper runs the same targeted checks:

```bash
./scripts/test-apps.sh
```

## Pre-Commit

Install the repository hooks from the root:

```bash
uv run --project apps/dotdev --locked pre-commit install --config .pre-commit-config.yaml
```

The root pre-commit config runs Black and isort against Python files in each app using that app's own `uv` project.

## Docker

Validate the Compose file:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local config
```

Start the stack:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build
```

Inspect status:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local ps
```

Shut down:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local down
```

Use `down -v` only when you intentionally want to delete local database volumes.

## Raman Direct Run

Use direct mode when you are changing Raman code and do not need Caddy or the
rest of the platform stack:

```bash
cd apps/raman
cp .env.example .env
uv sync --locked
uv run pytest tests -q
ollama pull gemma4:26b
uv run raman-api
```

In another terminal:

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/chat --json '{"prompt":"say pong"}'
```

Direct mode reads `apps/raman/.env` because the process runs from the app
directory. Platform Compose reads root `.env.local` because Compose runs from
the monorepo root.

## Homi And Vikram Direct Runs

Use direct mode when changing one app and you do not need Caddy:

```bash
cd apps/homi
cp .env.example .env
uv sync --locked
uv run pytest tests -q
uv run homi-api
```

```bash
cd apps/vikram
cp .env.example .env
uv sync --locked
uv run pytest tests -q
uv run vikram-api
```

Both direct APIs listen on `http://127.0.0.1:8000`. Homi live calls require AWS
Bedrock credentials; Vikram live calls require `GOOGLE_API_KEY`.

## Smoke Tests

```bash
curl -I http://dotdev.localhost/
curl http://prefect.localhost/api/health
curl http://raman.localhost/healthz
curl http://homi.localhost/healthz
curl http://vikram.localhost/healthz
curl http://raman.localhost/chat --json '{"prompt":"say pong"}'
curl -I http://flow.localhost/
curl -I http://paperclip.localhost/
curl -I http://localhost:8501/
curl http://localhost:8000/healthz
curl http://localhost:8001/healthz
curl http://localhost:8002/healthz
curl http://localhost:3100/api/health
curl http://localhost:4200/api/health
curl -I http://localhost:8080/
```

Paperclip should return `401` through `http://paperclip.localhost/` until Caddy basic auth credentials are supplied, and `http://localhost:3100/api/health` should reach the direct container health endpoint. Airflow may return a redirect or login response depending on auth state; the webserver should be reachable and the scheduler container should be running.

After Paperclip is running, generate the first local admin invite inside the container:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local exec paperclip pnpm paperclipai auth bootstrap-ceo --config /etc/paperclip/config.json --base-url http://paperclip.localhost
```

Redeem the invite through `http://paperclip.localhost` using the local Caddy credentials. Do not paste invite URLs into logs, issues, or chat.
