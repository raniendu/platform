# Platform

A personal monorepo of small, independent Python apps that share one deployment
setup. Each app keeps its own dependencies and tests; everything ships together
to a single host behind one reverse proxy.

Local development is Docker-first and mirrors the production layout, so the same
Compose stack you run on your machine is the one that runs in production.

## Apps

| App | What it is | Stack |
| --- | --- | --- |
| `apps/dotdev/` | Personal website | Flask, Python 3.13 |
| `apps/raman/` | Personal AI agent (HTTP + Telegram) | FastAPI + Pydantic AI, Python 3.13 |
| `apps/prefect/` | Prefect flows, server, and worker | Prefect, Python 3.10+ |
| `apps/flow/` | Airflow DAGs and image | Airflow, Python 3.10+ |

## Repository Layout

- `apps/` - the apps above, each self-contained with its own `pyproject.toml`.
- `deploy/compose/` - local and production Docker Compose files.
- `deploy/caddy/` - Caddy routing for local and production.
- `infra/terraform/` - infrastructure definitions.
- `.github/workflows/` - CI and deploy workflows.
- `scripts/` - root helpers for syncing apps, running tests, and local Compose.
- `docs/` - architecture, runbooks, and per-app docs (start at `docs/README.md`).

## Quick Start

You need `uv` and Docker Desktop. Create local env values, install per-app
Python environments, and run the test suites:

```bash
cp .env.example .env.local
./scripts/sync-apps.sh --locked
./scripts/test-apps.sh
```

Start the shared local stack:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build
```

Apps are served through Caddy on friendly hostnames:

- DotDev: `http://dotdev.localhost`
- Prefect: `http://prefect.localhost`
- Raman: `http://raman.localhost`
- Airflow: `http://flow.localhost`

Container ports are also exposed directly for quick smoke checks:

- DotDev: `http://localhost:8501`
- Raman: `http://localhost:8000/healthz`
- Prefect: `http://localhost:4200/api/health`
- Airflow: `http://localhost:8080`
- Jaeger: `http://localhost:16686`

## Working on One App

Use the per-app `uv` project when you're changing a single app:

```bash
uv sync --project apps/dotdev
uv run --project apps/dotdev pytest apps/dotdev/tests -q

uv sync --project apps/raman
uv run --project apps/raman pytest apps/raman/tests -q

uv sync --project apps/prefect
uv run --project apps/prefect pytest apps/prefect/tests/property/

uv sync --project apps/flow
uv run --project apps/flow python apps/flow/scripts/validate-dags.py
uv run --project apps/flow pytest apps/flow/tests/
```

Validate or inspect the local stack without rebuilding:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local config
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local ps
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local down
```

## Running Raman Locally

Raman has two local run modes that use different env files:

- Repo-root Compose uses the root `.env.local`.
- Direct app development from `apps/raman/` uses `apps/raman/.env`.

Through the platform container:

```bash
cp .env.example .env.local
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build raman
curl http://localhost:8000/healthz
curl http://localhost:8000/chat --json '{"prompt":"say pong"}'
```

Direct app development:

```bash
cd apps/raman
cp .env.example .env
uv sync --locked
uv run pytest tests -q
uv run raman-api
```

The two modes also point at Ollama differently: use
`OLLAMA_BASE_URL=http://host.docker.internal:11434/v1` in the root `.env.local`
for Docker, and `OLLAMA_BASE_URL=http://localhost:11434/v1` in `apps/raman/.env`
for direct `uv` runs.

## Production

The public site and apps live at:

- DotDev: `https://raniendu.dev`
- Prefect: `https://prefect.raniendu.dev`
- Raman: `https://raman.raniendu.dev`
- Airflow: `https://flow.raniendu.dev`
- Jaeger: `https://jaeger.raniendu.dev`

Pushing to `main` deploys automatically. A manual redeploy is available too:

```bash
gh workflow run deploy.yml --repo raniendu/platform --ref main
gh run watch --repo raniendu/platform --exit-status
```

Infrastructure changes go through reviewed PRs and GitHub Actions — local
`doctl` is read-only and not used for writes. See the runbooks below for host,
DNS, secret, and rollback details.

## Documentation

Start at [docs/README.md](docs/README.md) for the full map. The most useful
runbooks:

- [Architecture](docs/architecture.md) - how the pieces fit together.
- [Local development](docs/local-development.md) - run the stack on your machine.
- [Developer guide](docs/developer-guide.md) - per-app workflows.
- [Deployment](docs/deployment.md) and [Operations](docs/operations.md) - ship and run production.
- [Secrets](docs/secrets.md) and [Rollback](docs/rollback.md) - credentials and recovery.
- [Cloud architecture recommendation](docs/cloud-architecture-recommendation.md) - hosting and cost tradeoffs.
- Per-app architecture under [docs/apps/](docs/apps/README.md); datastore ownership under [docs/database/](docs/database/README.md).
