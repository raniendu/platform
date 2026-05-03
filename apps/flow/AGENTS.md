# Airflow App Agent Guide

## Scope

This guide applies inside `apps/flow/`. The root `AGENTS.md` remains authoritative for shared monorepo, deployment, infrastructure, and secret-handling rules.

## Project Shape

- `dags/`: Airflow DAG definitions.
- `scripts/validate-dags.py`: DAG import validation.
- `tests/`: Airflow DAG and behavior tests.
- `Dockerfile`: Airflow image source used by the shared platform workflows.

There is no standalone Airflow Terraform state, `infra_enabled` toggle, or independent production Droplet in this app directory.

## Commands

Run from the repository root:

```bash
uv sync --project apps/flow
uv run --project apps/flow python apps/flow/scripts/validate-dags.py
uv run --project apps/flow pytest apps/flow/tests/
```

Local platform stack:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local logs -f airflow-webserver
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local logs -f airflow-scheduler
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local down
```

## Development Rules

- Keep DAG files under `dags/`.
- Validate DAG imports before reporting completion.
- Keep DAG imports lightweight; avoid expensive work at module import time.
- Do not hardcode credentials in DAGs. Use Airflow Variables, Connections, or environment-backed settings.
- Production Airflow runs with constrained parallelism for the 2 GiB Droplet, so avoid DAG designs that assume high local concurrency.

## Deployment Boundary

Production Airflow runs in the shared platform stack on `platform-shared`, behind Caddy at `https://flow.raniendu.dev`.

Do not add standalone DigitalOcean deployment instructions here. Production deploys use the root `.github/workflows/deploy.yml` workflow after review and environment approval.

Local DigitalOcean CLI usage is read-only only. Infrastructure writes must go through reviewed PRs and GitHub Actions.
