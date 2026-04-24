# Local Development

## Prerequisites

- Docker Desktop with Compose v2.
- `uv` installed locally.
- Ports `80`, `4200`, `8080`, and `8501` available.

## Environment

Create local environment values from the example file:

```bash
cp .env.example .env.local
```

Keep `.env.local` untracked. Empty API keys are acceptable for local container startup; flows that call Gemini or Pushover need real values before execution.

## Python Environments

Each app keeps its own `pyproject.toml` and `uv.lock`.

```bash
uv sync --project apps/dotdev
uv sync --project apps/prefect
uv sync --project apps/flow
```

The root helper runs all three:

```bash
./scripts/sync-apps.sh
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
curl -I http://localhost:8501/
curl http://localhost:4200/api/health
curl -I http://localhost:8080/
```

Airflow may return a redirect or login response depending on auth state; the webserver should be reachable and the scheduler container should be running.
