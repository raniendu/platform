# Platform

Monorepo for the services previously split across `dotDev`, `prefect`, and `flow`.

Production runs on a single DigitalOcean Droplet managed by Terraform and deployed from GitHub Actions with Docker Compose. Local development remains Docker-first and uses the same app layout as production.

## Layout

- `apps/dotdev/` - Flask personal site, Python 3.13.
- `apps/prefect/` - Prefect flows, config, worker scripts, Python 3.10+.
- `apps/flow/` - Airflow DAGs and image, Python 3.10+.
- `deploy/compose/` - shared local and production Docker Compose files.
- `deploy/caddy/` - Caddy routing for local and production.
- `infra/terraform/` - shared DigitalOcean Droplet infrastructure.
- `.github/workflows/` - CI and manual production deploy workflows.
- `docs/` - architecture, developer guide, cloud recommendation, local development, deployment, DNS, secrets, rollback, operations, cost comparison, and deprecation docs.
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

## Production

Public routes:

- DotDev: `https://raniendu.dev`
- Prefect: `https://prefect.raniendu.dev`
- Airflow: `https://flow.raniendu.dev`

Manual redeploy:

```bash
gh workflow run deploy.yml --repo raniendu/platform --ref main
gh run watch --repo raniendu/platform --exit-status
```

The deploy workflow temporarily allowlists the GitHub runner for SSH, uploads the repo and production env file, starts production Compose, force-recreates Caddy, runs public smoke checks, and removes the temporary SSH firewall rule in an `always()` cleanup step.

Cloud provider architecture and cost tradeoffs are summarized in `docs/cloud-architecture-recommendation.md`.
Developer workflows are covered in `docs/developer-guide.md`. DigitalOcean cost comparison and old-resource deprecation are covered in `docs/digitalocean-cost-comparison.md` and `docs/deprecation-plan.md`.
