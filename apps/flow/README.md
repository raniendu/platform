# Airflow App

This directory contains the Apache Airflow DAGs, tests, validation script, and image definition used by the `platform` monorepo.

Airflow is no longer deployed as a standalone DigitalOcean project. Production runs inside the shared `platform` stack on the `platform-shared` Droplet, behind Caddy at:

- `https://flow.raniendu.dev`

## Runtime Model

Local development:

- built from `apps/flow/Dockerfile`;
- runs `airflow-init`, `airflow-webserver`, `airflow-scheduler`, and local `airflow-postgres`;
- mounts `apps/flow/dags` into the Airflow containers;
- is routed by local Caddy at `http://flow.localhost`;
- also exposes `http://localhost:8080` for direct local checks.

Production:

- uses SHA-pinned GHCR images built by GitHub Actions;
- runs `airflow-init`, `airflow-webserver`, and `airflow-scheduler` in `deploy/compose/docker-compose.prod.yml`;
- stores metadata in the shared `platform-postgres` container, database `airflow`, role `airflow`;
- uses conservative scheduler/parallelism settings for the current 2 GiB Droplet;
- is deployed only by the manual `.github/workflows/deploy.yml` workflow.

Do not run DigitalOcean write operations from a local machine for this app. Infrastructure changes go through reviewed GitHub PRs and GitHub Actions.

## Quick Start

Run these commands from the repository root.

```bash
cp .env.example .env.local
uv sync --project apps/flow
uv run --project apps/flow python apps/flow/scripts/validate-dags.py
uv run --project apps/flow pytest apps/flow/tests/
```

Start the full local platform stack:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build
```

Useful local URLs:

- Airflow UI through Caddy: `http://flow.localhost`
- Airflow UI directly: `http://localhost:8080`
- Health: `http://localhost:8080/health`

Local Airflow uses the simple auth manager in all-admins mode. Enter any username.

Stop the stack:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local down
```

## DAG Development

Add DAGs under `apps/flow/dags/`.

Validate imports before committing:

```bash
uv run --project apps/flow python apps/flow/scripts/validate-dags.py
```

Run tests:

```bash
uv run --project apps/flow pytest apps/flow/tests/
```

Useful logs:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local logs -f airflow-webserver
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local logs -f airflow-scheduler
```

## Production Deployment

Production deployment is manual from the root workflow, not automatic on every push:

```bash
gh workflow run deploy.yml --repo raniendu/platform --ref main
gh run watch --repo raniendu/platform --exit-status
```

The workflow builds the Airflow image, deploys it with the DotDev and Prefect images, uploads `PLATFORM_ENV_FILE`, starts Docker Compose on `/opt/platform`, and runs public smoke checks.

Use these root docs for production work:

- `docs/deployment.md`
- `docs/secrets.md`
- `docs/operations.md`
- `docs/rollback.md`

## Project Structure

```text
apps/flow/
├── dags/               # Airflow DAG definitions
├── scripts/            # DAG validation and utility scripts
├── tests/              # DAG and behavior tests
├── Dockerfile          # Airflow image source
├── pyproject.toml      # uv-managed dependencies
└── uv.lock
```

## Airflow Version

The image currently pins Apache Airflow `3.1.7` on Python `3.10`.

Airflow 3 uses:

- `airflow api-server` rather than the old `airflow webserver` command;
- `/api/v2` for API v2 paths;
- `airflow db migrate` for database migrations.

## Cost

Airflow has no standalone DigitalOcean bill. It shares the current production Droplet with DotDev and Prefect:

- `platform-shared`, `s-1vcpu-2gb`;
- weekly Droplet backups enabled;
- estimated shared platform cost: about `$14.40/month` before taxes and unusual bandwidth.

See `docs/digitalocean-cost-comparison.md` for the current inventory and cost notes.
