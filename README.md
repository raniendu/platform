# Platform

Local-first monorepo for the services currently split across `dotDev`, `prefect`, and `flow`.

No GitHub remote or DigitalOcean resource changes are part of this local bootstrap. The first gate is proving the local Docker stack works.

## Layout

- `apps/dotdev/` - Flask personal site, Python 3.13.
- `apps/prefect/` - Prefect flows, config, worker scripts, Python 3.10+.
- `apps/flow/` - Airflow DAGs and image, Python 3.10+.
- `deploy/compose/` - shared local and production Docker Compose files.
- `deploy/caddy/` - Caddy routing for local and production.
- `infra/terraform/` - shared DigitalOcean Droplet infrastructure.
- `.github/workflows/` - CI and manual deploy workflows after GitHub repo creation.
- `docs/` - architecture, cloud recommendation, local development, deployment, DNS, secrets, rollback, and operations runbooks.
- `scripts/` - root helpers for uv, tests, and local Compose.

## Quick Start

Install `uv` and Docker Desktop, then create local env values:

```bash
cp .env.example .env.local
```

Install per-app Python environments:

```bash
./scripts/sync-apps.sh
```

Run targeted checks:

```bash
./scripts/test-apps.sh
```

Start the shared local stack:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build
```

Local service URLs:

- DotDev: `http://dotdev.localhost`
- Prefect: `http://prefect.localhost`
- Airflow: `http://flow.localhost`

Direct container ports are also exposed for smoke checks:

- DotDev: `http://localhost:8501`
- Prefect: `http://localhost:4200/api/health`
- Airflow: `http://localhost:8080`

## Common Commands

```bash
uv sync --project apps/dotdev
uv run --project apps/dotdev pytest apps/dotdev/tests -q

uv sync --project apps/prefect
uv run --project apps/prefect pytest apps/prefect/tests/property/

uv sync --project apps/flow
uv run --project apps/flow python apps/flow/scripts/validate-dags.py
uv run --project apps/flow pytest apps/flow/tests/

docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local config
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local ps
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local down
```

## Gates

GitHub repo creation is blocked until the local Docker stack is built, running, and smoke-tested. DigitalOcean and Squarespace changes remain blocked by later human approval gates described in `docs/deployment.md` and `docs/dns-cutover.md`.

Cloud provider architecture and cost tradeoffs are summarized in `docs/cloud-architecture-recommendation.md`.
