# Platform Agent Guide

## Scope

This file applies to the whole `platform` monorepo. More specific `AGENTS.md` files under `apps/dotdev/`, `apps/prefect/`, and `apps/flow/` apply inside those app directories, but this root guide is the source of truth for shared monorepo, deployment, infrastructure, and secret-handling work.

## Repository Shape

- `apps/dotdev/`: Flask personal site, Python 3.13.
- `apps/prefect/`: Prefect flows, server/worker image, Python 3.10+.
- `apps/flow/`: Airflow DAGs and image, Python 3.10+.
- `deploy/compose/`: local and production Docker Compose files.
- `deploy/caddy/`: local and production Caddy routing.
- `infra/terraform/`: DigitalOcean Droplet and firewall infrastructure.
- `docs/`: architecture, developer guide, deployment, DNS, secrets, rollback, operations, cloud recommendation, DigitalOcean cost comparison, and deprecation docs.
- `.github/workflows/`: CI and manual production deploy workflows.

## Tooling Rules

- Use `uv` for Python dependency sync and test execution.
- Keep each app's own `pyproject.toml` and `uv.lock`; do not introduce a shared Python package unless real duplication justifies it.
- Use root commands for monorepo validation:
  - `./scripts/sync-apps.sh`
  - `./scripts/test-apps.sh`
  - `docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local config`
  - `docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production.generated config`
- Use targeted app commands when changing one app:
  - DotDev: `uv run --project apps/dotdev pytest apps/dotdev/tests -q`
  - Prefect: `uv run --project apps/prefect pytest apps/prefect/tests/property/`
  - Airflow: `uv run --project apps/flow python apps/flow/scripts/validate-dags.py` and `uv run --project apps/flow pytest apps/flow/tests/`

## Deployment And Infrastructure

- DigitalOcean single-Droplet Docker Compose deployment is the current production path.
- Terraform lives in `infra/terraform`; do not run `terraform apply` without explicit user approval.
- The production deploy workflow is manual: `.github/workflows/deploy.yml`.
- The deploy workflow temporarily allowlists the GitHub runner `/32` in the DigitalOcean firewall, deploys over SSH, recreates Caddy, runs public smoke checks, then removes the temporary rule. Do not replace this with `0.0.0.0/0` SSH access.
- Production DNS is managed manually in Squarespace. Apex/root must be an `A` record to the Droplet IP, not an `ALIAS` record to an IP address.
- Do not change or delete old production resources unless the user explicitly approves the specific decommissioning step.
- `www.raniendu.dev` redirects to `https://raniendu.dev{uri}` in Caddy.

## Secrets And Local Files

- Never print, commit, or paste values from `.env.local`, `.env.production.generated`, `.env.production.credentials`, Terraform state, SSH keys, or GitHub secrets.
- `.env.production.generated` is the source used for the GitHub `PLATFORM_ENV_FILE` secret.
- `.env.production.credentials` stores generated human login credentials. If the user needs a value, direct them to read it locally rather than pasting it into chat.
- Caddy bcrypt hashes in Compose env files must escape dollar signs as `$$`.
- Google Maps is intentionally not implemented and should not be reintroduced.

## Change Hygiene

- Keep app-specific logic inside its app directory.
- Keep shared runtime/deployment changes under `deploy/`, `.github/workflows/`, `infra/`, or `docs/`.
- Update docs with any deployment, DNS, secret, Terraform, or operations behavior change.
- Prefer small, focused commits when the user asks to commit. Do not commit or push without explicit user request.
- Preserve unrelated local changes and ignored runtime state.

## Verification Expectations

Before reporting completion, run the narrowest useful checks for the changed area and state what passed. For production-impacting changes, also verify:

- GitHub CI/deploy status when workflows are touched.
- `docker compose ... config` for local and/or production Compose changes.
- Caddy syntax for Caddyfile changes.
- Terraform `plan` for Terraform changes, with no unapproved apply.
- Production smoke checks after an approved deploy.
- DigitalOcean inventory checks before cost or deprecation claims: Droplets, App Platform apps, databases, volumes, load balancers, snapshots/backups, and firewall rules.
