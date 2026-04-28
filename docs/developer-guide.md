# Developer Guide

This guide covers day-to-day development for the `platform` monorepo.

## Prerequisites

- `uv`
- Docker Desktop
- GitHub CLI, authenticated as an account with access to `raniendu/platform`
- `doctl`, authenticated for read-only checks and approved infrastructure operations
- Terraform, only for changes under `infra/terraform`

Do not commit `.env.local`, `.env.production.generated`, `.env.production.credentials`, Terraform state, SSH keys, or copied secret values.

## Repository Layout

- `apps/dotdev/`: Flask site, Python 3.13.
- `apps/prefect/`: Prefect server/worker image and flows, Python 3.10+.
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

Sync all app environments:

```bash
./scripts/sync-apps.sh
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

Airflow:

```bash
uv sync --project apps/flow
uv run --project apps/flow python apps/flow/scripts/validate-dags.py
uv run --project apps/flow pytest apps/flow/tests/
```

Compose validation:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local config
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production.generated config
```

## Production Deploys

Production deploys are manual GitHub Actions runs. The workflow applies Terraform first, then deploys the app stack:

```bash
gh workflow run deploy.yml --repo raniendu/platform --ref main
gh run watch --repo raniendu/platform --exit-status
```

The deploy workflow:

1. Builds DotDev, Prefect, and Airflow images in GitHub Actions and pushes them to GHCR with the current commit SHA tag.
2. After the GitHub `production` environment approval, adopts exactly one existing `platform-shared` Droplet/firewall into Terraform state, or creates one Droplet if none exists.
3. Refuses to apply if Terraform would delete/replace a Droplet, create a second Droplet, or if duplicate matching Droplets already exist.
4. Applies `infra/terraform`.
5. Temporarily allowlists the GitHub runner `/32` in the Terraform-managed DigitalOcean firewall.
6. Uploads the repository to `/opt/platform`.
7. Uploads `PLATFORM_ENV_FILE` to `/opt/platform/.env.production` and appends the SHA-pinned image refs.
8. Uploads temporary GHCR credentials, pulls images on the Droplet, and runs production Docker Compose with `up -d --no-build`.
9. Force-recreates Caddy so Caddyfile updates are picked up.
10. Runs public smoke checks.
11. Removes temporary GHCR credentials and the SSH firewall rule in `always()` cleanup steps.

Expected smoke results:

```text
raniendu.dev -> 200
www.raniendu.dev -> 301
prefect.raniendu.dev/api/health -> 401
flow.raniendu.dev -> 200
```

The Prefect `401` is expected because Caddy basic auth protects the route.

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
curl -sS -o /dev/null -w '%{http_code}\n' https://flow.raniendu.dev/
```

## Infrastructure Changes

Terraform is under `infra/terraform`.

```bash
cd infra/terraform
terraform init
terraform plan -var-file=terraform.tfvars
```

Normal production applies run through `deploy.yml`, which first imports the existing named Droplet/firewall and then applies the plan. Do not widen SSH access to `0.0.0.0/0`; the deploy workflow handles temporary GitHub runner access.

## Secrets

Use `docs/secrets.md` for required names and rotation notes. If a password or key is needed, read it from the local ignored credentials file or the provider UI. Do not paste secrets into issues, docs, commits, or chat.

Google Maps is intentionally not implemented in the monorepo.
