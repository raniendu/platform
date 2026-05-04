# Local Development

## Prerequisites

- Docker Desktop with Compose v2.
- `uv` installed locally.
- Ports `80`, `3100`, `4200`, `8080`, and `8501` available.

## Environment

Create local environment values from the example file:

```bash
cp .env.example .env.local
```

Keep `.env.local` untracked. Empty API keys are acceptable for local container startup; flows that call Gemini or Pushover need real values before execution. Paperclip can also pass through `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `GEMINI_API_KEY` when you want provider-backed agent features locally.

The example file includes local Paperclip Caddy credentials with user `admin` and password `paperclip_local`. Change them in `.env.local` if needed.

## Python Environments

Each app keeps its own `pyproject.toml`, `uv.lock`, and virtual environment. This avoids forcing the Flask site, Prefect flows, and Airflow image into one shared Python resolution.

```bash
uv sync --project apps/dotdev
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

## Tests

```bash
uv run --project apps/dotdev pytest apps/dotdev/tests -q
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

## Smoke Tests

```bash
curl -I http://dotdev.localhost/
curl http://prefect.localhost/api/health
curl -I http://flow.localhost/
curl -I http://paperclip.localhost/
curl -I http://localhost:8501/
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
