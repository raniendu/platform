# Prefect App Agent Guide

## Scope

This guide applies inside `apps/prefect/`. The root `AGENTS.md` remains authoritative for shared monorepo, deployment, infrastructure, and secret-handling rules.

## Project Shape

- `flows/`: Prefect flow definitions.
- `config/`: Pydantic settings and environment detection.
- `docker/`: container startup scripts, including the Prefect worker entrypoint.
- `scripts/deploy-flows.py`: deployment registration.
- `tests/`: property and integration tests.
- `Dockerfile`: image source used by the shared platform workflows.

There is no standalone Prefect Terraform or production Compose stack in this app directory.

## Commands

Run from the repository root:

```bash
uv sync --project apps/prefect
uv run --project apps/prefect pytest apps/prefect/tests/property/
uv run --project apps/prefect pytest apps/prefect/tests/integration/
```

Local platform stack:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local logs -f prefect-server
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local down
```

## Development Rules

- Keep flows in `flows/*.py` with descriptive `@flow(name="...")` names.
- Put provider and environment configuration in `config/`; avoid hardcoded secrets or environment-specific URLs in flow logic.
- Keep the daily brief verification gate intact: no source URL means no rendered headline.
- Add or update tests for provider, rendering, deployment-registration, or settings changes.

## Deployment Boundary

Production Prefect runs in the shared platform stack on `platform-shared`, behind Caddy at `https://prefect.raniendu.dev`.

Do not add standalone DigitalOcean deployment instructions here. Production deploys use the root `.github/workflows/deploy.yml` workflow after review and environment approval.

Local DigitalOcean CLI usage is read-only only. Infrastructure writes must go through reviewed PRs and GitHub Actions.
