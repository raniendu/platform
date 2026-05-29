# Local Development

## Prerequisites

- Docker Desktop with Compose v2.
- `uv` installed locally.
- Ports `80`, `4200`, `8000`, `8080`, and `8501` available.

## Environment

Create local environment values from the example file:

```bash
cp .env.example .env.local
```

Keep `.env.local` untracked. Empty API keys are acceptable for local container startup; flows that call Gemini or Pushover need real values before execution. Raman local Compose builds `apps/raman` and defaults to a host Ollama server at `http://host.docker.internal:11434/v1`.

Use one environment file per execution mode:

| Mode | Env file | Use for |
| --- | --- | --- |
| Platform Compose | root `.env.local` | Running the shared local stack and Caddy routes |
| Raman direct run | `apps/raman/.env` | Iterating on Raman without Compose |

Raman has a separate app-level env file for direct `uv` runs:

```bash
cp apps/raman/.env.example apps/raman/.env
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

## Choosing A Local Path

- Use full Compose when changing routing, Compose env, Caddy, Prefect,
  Airflow, or cross-app behavior.
- Use direct app runs when changing Raman Python code and you only need one
  FastAPI process.
- Use app-specific tests before full local Compose when the change is isolated
  to one app.
- Use `docker compose ... config` before changing Compose, Caddy, or env-file
  behavior; it catches interpolation and profile mistakes without starting
  containers.

## Raman Direct Run

Use direct mode when you are changing Raman code and do not need Caddy or the
rest of the platform stack:

```bash
cd apps/raman
cp .env.example .env
uv sync --locked
uv run pytest tests -q
ollama pull gemma4:26b-mlx
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

## Smoke Tests

```bash
curl -I http://dotdev.localhost/
curl http://prefect.localhost/api/health
curl http://raman.localhost/healthz
curl http://raman.localhost/chat --json '{"prompt":"say pong"}'
curl -I http://flow.localhost/
curl -I http://localhost:8501/
curl http://localhost:8000/healthz
curl http://localhost:4200/api/health
curl -I http://localhost:8080/
```

Airflow may return a redirect or login response depending on auth state; the webserver should be reachable and the scheduler container should be running.

When you intentionally start only a subset of local services, skip smoke checks
for services you did not start. For production profile behavior and disabled-app
`404` expectations, use [operations](operations.md).
