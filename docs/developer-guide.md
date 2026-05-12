# Developer Guide

This guide covers day-to-day development for the `platform` monorepo.

## Prerequisites

- `uv`
- Docker Desktop
- GitHub CLI, authenticated as an account with access to `raniendu/platform`
- `doctl`, authenticated for read-only inventory checks only
- Terraform, only for changes under `infra/terraform`

Do not commit `.env.local`, `.env.production.generated`, `.env.production.credentials`, Terraform state, SSH keys, or copied secret values.

## Repository Layout

- `apps/dotdev/`: Flask site, Python 3.13.
- `apps/raman/`: Pydantic AI agent with FastAPI, Telegram webhook, and threaded SQLite/DBOS state, Python 3.13.
- `apps/homi/`: Strands SDK agent with the same FastAPI, Telegram, and threaded SQLite/DBOS surface as Raman, Python 3.13.
- `apps/vikram/`: Google ADK agent with the same FastAPI, Telegram, and threaded SQLite/DBOS surface as Raman, Python 3.13.
- `apps/prefect/`: Prefect server/worker image and flows, Python 3.10+.
- `apps/paperclip/`: Dockerfile that builds upstream Paperclip.
- `apps/flow/`: Airflow DAGs, image, and DAG validation script, Python 3.10+.
- `deploy/compose/`: local and production Compose files.
- `deploy/caddy/`: local and production routing.
- `.github/workflows/`: CI and manual deploy workflows.
- `infra/terraform/`: DigitalOcean Droplet and firewall.
- `docs/`: runbooks and architecture notes.

## Local Setup

Create a local env file:

```bash
cp .env.example .env.local
```

Use root `.env.local` for Docker Compose. If you run Raman directly with `uv`,
Homi directly, or Vikram directly, also create the app-local env file:

```bash
cp apps/raman/.env.example apps/raman/.env
cp apps/homi/.env.example apps/homi/.env
cp apps/vikram/.env.example apps/vikram/.env
```

Keep `OLLAMA_BASE_URL=http://host.docker.internal:11434/v1` in root
`.env.local` for the container and `OLLAMA_BASE_URL=http://localhost:11434/v1`
in `apps/raman/.env` for direct Mac processes.

Sync all app environments:

```bash
./scripts/sync-apps.sh --locked
```

Run the app test suites:

```bash
./scripts/test-apps.sh
```

Start the local stack:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build
```

Local routes:

- `http://dotdev.localhost`
- `http://prefect.localhost`
- `http://raman.localhost`
- `http://homi.localhost`
- `http://vikram.localhost`
- `http://paperclip.localhost`
- `http://flow.localhost`

Stop the local stack:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local down
```

## App Commands

DotDev:

```bash
uv sync --project apps/dotdev
uv run --project apps/dotdev pytest apps/dotdev/tests -q
```

Prefect:

```bash
uv sync --project apps/prefect
uv run --project apps/prefect pytest apps/prefect/tests/property/
```

Paperclip:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build paperclip paperclip-postgres
curl http://localhost:3100/api/health
```

Raman:

```bash
uv sync --project apps/raman
uv run --project apps/raman pytest apps/raman/tests -q
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d raman
curl http://localhost:8000/healthz
```

For direct Raman development:

```bash
cd apps/raman
cp .env.example .env
uv sync --locked
uv run pytest tests -q
uv run raman-api
```

Homi:

```bash
uv sync --project apps/homi
uv run --project apps/homi pytest apps/homi/tests -q
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d homi
curl http://localhost:8001/healthz
```

For direct Homi development:

```bash
cd apps/homi
cp .env.example .env
uv sync --locked
uv run pytest tests -q
uv run homi-api
```

Vikram:

```bash
uv sync --project apps/vikram
uv run --project apps/vikram pytest apps/vikram/tests -q
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d vikram
curl http://localhost:8002/healthz
```

For direct Vikram development:

```bash
cd apps/vikram
cp .env.example .env
uv sync --locked
uv run pytest tests -q
uv run vikram-api
```

Then, from another terminal:

```bash
curl http://127.0.0.1:8000/healthz
```

If `./scripts/sync-apps.sh --locked` prints `VIRTUAL_ENV` mismatch warnings,
deactivate the currently active app venv and rerun it. The warnings are not
failures; `uv` is protecting the per-app virtualenv layout.

Airflow:

```bash
uv sync --project apps/flow
uv run --project apps/flow python apps/flow/scripts/validate-dags.py
uv run --project apps/flow pytest apps/flow/tests/
```

Compose validation:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local config
bash deploy/scripts/render-prod-caddy.sh deploy/apps.prod.env deploy/caddy/prod-sites
RAMAN_IMAGE=ghcr.io/raniendu/platform/raman:ci HOMI_IMAGE=ghcr.io/raniendu/platform/homi:ci VIKRAM_IMAGE=ghcr.io/raniendu/platform/vikram:ci COMPOSE_PROFILES=dotdev,prefect,raman docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.example config
```

## Production Deploys

Production deploys are manual GitHub Actions runs. The workflow applies Terraform first, then deploys the app stack:

```bash
gh workflow run deploy.yml --repo raniendu/platform --ref main
gh run watch --repo raniendu/platform --exit-status
```

The deploy workflow:

1. Reads `deploy/apps.prod.env`, builds enabled in-repo app images in GitHub Actions, and pushes them to GHCR with the current commit SHA tag.
2. After the GitHub `production` environment approval, reads DigitalOcean inventory and adopts exactly one existing `platform-shared` Droplet/firewall into Terraform state, or creates one Droplet if none exists.
3. Refuses to apply if Terraform would delete/replace a Droplet, create a second Droplet, if duplicate matching Droplets already exist, or if the smaller-Droplet staging host `platform-shared-small` exists.
4. Applies `infra/terraform`.
5. Temporarily allowlists the GitHub runner `/32` in the Terraform-managed DigitalOcean firewall.
6. Uploads the repository to `/opt/platform`.
7. Uploads `PLATFORM_ENV_FILE` to `/opt/platform/.env.production` and appends app deploy flags and SHA-pinned image refs.
8. Uploads temporary GHCR credentials, renders enabled/disabled Caddy routes, stops disabled app containers, and pulls enabled images on the Droplet.
9. Runs the one-time Postgres consolidation when the host still has separate Prefect and Airflow Postgres containers.
10. Runs the idempotent Paperclip database initializer only when Paperclip is enabled.
11. Runs production Docker Compose with `COMPOSE_PROFILES` matching enabled app flags and `up -d --no-build`.
12. Force-recreates Caddy so Caddyfile updates are picked up.
13. Runs public smoke checks, then stops legacy Postgres containers after a successful migration.
14. Removes temporary GHCR credentials and the SSH firewall rule in `always()` cleanup steps.

Expected smoke results:

```text
raniendu.dev -> 200
www.raniendu.dev -> 301
prefect.raniendu.dev/api/health -> 401
raman.raniendu.dev/healthz -> 200
homi.raniendu.dev -> 404
vikram.raniendu.dev -> 404
paperclip.raniendu.dev -> 404
flow.raniendu.dev -> 404
```

With the current `deploy/apps.prod.env`, Prefect's `401` response is expected because Caddy basic auth protects that route; Raman returns `200` from `/healthz`; Homi, Vikram, Paperclip, and Flow return `404` because they are disabled.

The `s-1vcpu-2gb` migration completed on 2026-05-02. Use `deploy.yml` for routine production releases. Keep `migrate-smaller-droplet.yml` only for future new-Droplet migrations or recovery; it stages `platform-shared-small`, waits for manual DNS cutover, promotes it back to canonical `platform-shared`, and deletes the retired Droplet only in a separate typed-confirmation phase.

## Production Checks

GitHub:

```bash
gh workflow list --repo raniendu/platform
gh run list --repo raniendu/platform --limit 8
gh secret list --repo raniendu/platform --env production
gh variable list --repo raniendu/platform --env production
```

DigitalOcean inventory:

```bash
doctl compute droplet list
doctl compute firewall get f08d6940-f470-47ce-8dba-ffad3ef16832
doctl apps list
doctl databases list
doctl compute volume list
doctl compute load-balancer list
doctl compute snapshot list
```

Public endpoints:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://raniendu.dev/
curl -sS -o /dev/null -w '%{http_code}\n' https://www.raniendu.dev/
curl -sS -o /dev/null -w '%{http_code}\n' https://prefect.raniendu.dev/api/health
curl -sS -o /dev/null -w '%{http_code}\n' https://paperclip.raniendu.dev/
curl -sS -o /dev/null -w '%{http_code}\n' https://flow.raniendu.dev/
```

## Infrastructure Changes

Terraform is under `infra/terraform`.

```bash
cd infra/terraform
terraform init
terraform plan -var-file=terraform.tfvars
```

Normal production applies run through `deploy.yml`, which first imports the existing named Droplet/firewall and then applies the plan. Do not run local DigitalOcean write operations for infra changes; reviewed PRs and GitHub Actions are the write path. Do not widen SSH access to `0.0.0.0/0`; the deploy workflow handles temporary GitHub runner access.

## Secrets

Use `docs/secrets.md` for required names and rotation notes. If a password or key is needed, read it from the local ignored credentials file or the provider UI. Do not paste secrets into issues, docs, commits, or chat.

Google Maps is intentionally not implemented in the monorepo.
