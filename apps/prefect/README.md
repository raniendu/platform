# Prefect App

This directory contains the Prefect flows, configuration, worker startup code, and image definition used by the `platform` monorepo.

Prefect is no longer deployed as a standalone DigitalOcean project. Production runs inside the shared `platform` stack on the `platform-shared` Droplet, behind Caddy at:

- `https://prefect.raniendu.dev`

The production route is protected by Caddy basic auth. A `401` from `https://prefect.raniendu.dev/api/health` is expected in public smoke checks because auth happens before the Prefect health endpoint.

## Runtime Model

Local development:

- built from `apps/prefect/Dockerfile`;
- runs `prefect-server`, `prefect-worker`, and a local `prefect-postgres` container;
- is routed by local Caddy at `http://prefect.localhost`;
- also exposes `http://localhost:4200` for direct local checks.

Production:

- uses SHA-pinned GHCR images built by GitHub Actions;
- runs `prefect-server` and `prefect-worker` in `deploy/compose/docker-compose.prod.yml`;
- stores metadata in the shared `platform-postgres` container, database `prefect`, role `prefect`;
- is deployed only by the manual `.github/workflows/deploy.yml` workflow.

Do not run DigitalOcean write operations from a local machine for this app. Infrastructure changes go through reviewed GitHub PRs and GitHub Actions.

## Quick Start

Run these commands from the repository root.

```bash
cp .env.example .env.local
uv sync --project apps/prefect
uv run --project apps/prefect pytest apps/prefect/tests/property/
```

Start the full local platform stack:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build
```

Useful local URLs:

- Prefect UI through Caddy: `http://prefect.localhost`
- Prefect health directly: `http://localhost:4200/api/health`

Stop the stack:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local down
```

## Flow Development

Flows live under `apps/prefect/flows/`. Keep shared configuration in `apps/prefect/config/` and deployment registration logic in `apps/prefect/scripts/deploy-flows.py`.

Run a flow directly:

```bash
uv run --project apps/prefect python apps/prefect/flows/daily_brief.py
```

Run against the local Prefect server:

```bash
export PREFECT_API_URL=http://localhost:4200/api
uv run --project apps/prefect python apps/prefect/flows/daily_brief.py
```

Register local deployments:

```bash
PREFECT_API_URL=http://localhost:4200/api uv run --project apps/prefect python apps/prefect/scripts/deploy-flows.py
```

Set up local Pushover Secret blocks after exporting real credentials:

```bash
PREFECT_API_URL=http://localhost:4200/api uv run --project apps/prefect python apps/prefect/scripts/setup-blocks.py
```

## Daily Brief Verification Model

The `daily-brief` flow uses a grounded pipeline with a strict verification gate.

### Verification Features
- **No URL, no headline**: news candidates without a valid `source_url` are rejected.
- Every verified news item must include `headline`, `summary`, `source_url`, `publisher_name`, `published_timestamp`, and `evidence_snippet`.
- Candidates are verified before rendering; rejected candidates are excluded from user-facing output.
- If no verified items remain in a section, the flow renders a safe fallback (for example, `No verified updates available.`).

### Regional & Market Updates
- **Regional News**: Includes top headlines from **India** and technology updates from **Redmond, WA**.
- **Dynamic Markets**:
    - **Morning Brief (PST)**: Focuses on Indian markets (**Nifty 50**, **Sensex**).
    - **Afternoon Brief (PST)**: Focuses on US markets (**S&P 500**, **Nasdaq**).
- **Market Sourcing**: Facts are fetched from a structured source (Yahoo Finance chart API) and rendered directly.
- **LLM Summarization**: Uses Gemini 3 Flash to rewrite the rendered brief for readability while strictly adhering to the verified facts.

### Safe provider extension checklist

When adding a new news or market provider:

1. Return structured candidate records with source metadata and evidence snippets.
2. Route candidates through `verify_news_candidates` before rendering.
3. Keep deterministic checks (required fields, URL validity, evidence support) in front of any LLM step.
4. Ensure fallbacks are preserved when no verified records pass validation.

## Tests

```bash
uv run --project apps/prefect pytest apps/prefect/tests/property/
uv run --project apps/prefect pytest apps/prefect/tests/integration/
uv run --project apps/prefect pytest apps/prefect/tests/
```

Verification-focused tests for the daily brief:

```bash
uv run --project apps/prefect pytest apps/prefect/tests/property/test_daily_brief_behavior.py
```

## Production Deployment

Production deployment is manual from the root workflow, not automatic on every push:

```bash
gh workflow run deploy.yml --repo raniendu/platform --ref main
gh run watch --repo raniendu/platform --exit-status
```

The workflow builds the Prefect image, deploys it with the DotDev and Airflow images, uploads `PLATFORM_ENV_FILE`, starts Docker Compose on `/opt/platform`, and runs public smoke checks.

When Prefect is enabled, deployment also runs `apps/prefect/scripts/setup-blocks.py` inside the deployed worker before registering deployments. That step validates `PUSHOVER_APP_TOKEN` and `PUSHOVER_USER_KEY`, then refreshes the Prefect Secret blocks `pushover-app-token` and `pushover-user-key`. The daily brief reads those blocks first and uses env vars only as a rollout/local-development fallback.

Use these root docs for production work:

- `docs/deployment.md`
- `docs/secrets.md`
- `docs/operations.md`
- `docs/rollback.md`

## Project Structure

```text
apps/prefect/
├── config/             # Pydantic settings and environment helpers
├── docker/             # Prefect worker startup scripts
├── flows/              # Prefect flow definitions
├── scripts/            # Flow registration and utility scripts
├── tests/              # Property and integration tests
├── Dockerfile          # Production/local image source
├── pyproject.toml      # uv-managed dependencies
└── uv.lock
```

## Cost

Prefect has no standalone DigitalOcean bill. It shares the current production Droplet with DotDev and Airflow:

- `platform-shared`, `s-1vcpu-2gb`;
- weekly Droplet backups enabled;
- estimated shared platform cost: about `$14.40/month` before taxes and unusual bandwidth.

See `docs/digitalocean-cost-comparison.md` for the current inventory and cost notes.
