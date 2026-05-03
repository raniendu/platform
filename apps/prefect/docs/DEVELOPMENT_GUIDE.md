# Prefect Development Guide

This guide covers day-to-day Prefect flow development inside the `platform` monorepo.

## Current Deployment Assumptions

- Prefect is one app in the shared platform stack.
- Production is not a standalone Prefect Droplet, Terraform stack, or Nginx deployment.
- Local development uses `deploy/compose/docker-compose.local.yml`.
- Production uses `deploy/compose/docker-compose.prod.yml` and Caddy.
- Production deploys are manual GitHub Actions runs from `.github/workflows/deploy.yml`.

Run commands from the repository root unless a command says otherwise.

## Local Setup

```bash
cp .env.example .env.local
uv sync --project apps/prefect
```

Start the local platform:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build
```

Local Prefect URLs:

- UI through Caddy: `http://prefect.localhost`
- direct API health: `http://localhost:4200/api/health`

Follow logs:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local logs -f prefect-server
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local logs -f prefect-worker
```

Stop local services:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local down
```

## Creating Flows

Create new flows under `apps/prefect/flows/`.

```python
from prefect import flow, get_run_logger, task


@task
def transform_value(value: str) -> str:
    logger = get_run_logger()
    logger.info("Transforming value")
    return value.strip().upper()


@flow(name="example-flow", log_prints=True)
def example_flow(value: str = "hello") -> dict[str, str]:
    transformed = transform_value(value)
    return {"value": transformed}


if __name__ == "__main__":
    print(example_flow())
```

Use descriptive flow names, keep tasks small, and put provider/API settings in `apps/prefect/config/` instead of hardcoding them inside flow bodies.

## Running Flows Locally

Run directly without a persistent Prefect server:

```bash
uv run --project apps/prefect python apps/prefect/flows/daily_brief.py
```

Run against the local Prefect server:

```bash
export PREFECT_API_URL=http://localhost:4200/api
uv run --project apps/prefect python apps/prefect/flows/daily_brief.py
```

Register deployments against the local server:

```bash
PREFECT_API_URL=http://localhost:4200/api uv run --project apps/prefect python apps/prefect/scripts/deploy-flows.py
```

Trigger a registered deployment:

```bash
PREFECT_API_URL=http://localhost:4200/api uv run --project apps/prefect prefect deployment run "daily-brief/daily-brief"
```

If a deployment name differs, list available deployments first:

```bash
PREFECT_API_URL=http://localhost:4200/api uv run --project apps/prefect prefect deployment ls
```

## Testing

Run the focused property suite:

```bash
uv run --project apps/prefect pytest apps/prefect/tests/property/
```

Run integration tests:

```bash
uv run --project apps/prefect pytest apps/prefect/tests/integration/
```

Run all Prefect tests:

```bash
uv run --project apps/prefect pytest apps/prefect/tests/
```

For task-level tests, call Prefect tasks through `.fn()` when you want to exercise the underlying function without a Prefect engine run.

```python
from flows.example_flow import transform_value


def test_transform_value():
    assert transform_value.fn(" hello ") == "HELLO"
```

## Daily Brief Provider Rules

The daily brief flow has a verification gate for generated/news-like content:

- news candidates without a valid `source_url` are rejected;
- verified news records must include `headline`, `summary`, `source_url`, `publisher_name`, `published_timestamp`, and `evidence_snippet`;
- candidates are verified before rendering;
- fallback text is rendered when no verified candidates survive;
- market facts come from structured sources before prose rewriting.

When adding a provider, return structured candidate records first, then route them through the existing verification functions before user-facing output is assembled.

## Deployment

Do not deploy Prefect separately. Production deployment is the shared manual workflow:

```bash
gh workflow run deploy.yml --repo raniendu/platform --ref main
gh run watch --repo raniendu/platform --exit-status
```

Expected public smoke result for Prefect:

```text
prefect.raniendu.dev/api/health -> 401
```

`401` is expected because Caddy basic auth protects Prefect.

## Production Data

Local development uses a dedicated `prefect-postgres` container and local Docker volume.

Production uses the shared `platform-postgres` container with:

- database: `prefect`;
- role: `prefect`;
- password from `PREFECT_POSTGRES_PASSWORD` inside `PLATFORM_ENV_FILE`.

Do not paste production database credentials into docs, issues, commits, or chat.

## Removing Flows

1. Delete the flow file under `apps/prefect/flows/`.
2. Remove any deployment registration from `apps/prefect/scripts/deploy-flows.py`.
3. Run Prefect tests.
4. Deploy through the shared workflow after review and merge.

Old flow/deployment records may remain in the Prefect database until deleted from the UI or CLI.

## Useful Commands

```bash
uv sync --project apps/prefect
uv run --project apps/prefect pytest apps/prefect/tests/property/
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local logs -f prefect-server
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local logs -f prefect-worker
PREFECT_API_URL=http://localhost:4200/api uv run --project apps/prefect prefect flow-run ls
```
