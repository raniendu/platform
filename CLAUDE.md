# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`AGENTS.md` (root and per-app) is the source-of-truth guide for collaboration rules. This file is a fast orientation; defer to `AGENTS.md` and the docs it references when they conflict.

## Repository Shape

Monorepo of independent Python apps, each with its own `pyproject.toml` and `uv.lock` (no shared Python package):

- `apps/dotdev/` — Flask personal site, Python 3.13.
- `apps/raman/` — FastAPI + Pydantic AI agent (HTTP/Telegram), Python 3.13.
- `apps/prefect/` — Prefect server/worker + flows, Python 3.10+.
- `apps/flow/` — Apache Airflow DAGs and image, Python 3.10+.
- `deploy/compose/` — `docker-compose.local.yml` and `docker-compose.prod.yml`.
- `deploy/caddy/` — `Caddyfile.local`, `Caddyfile.prod`, `prod-sites/` (rendered at deploy).
- `deploy/apps.prod.env` — tracked production app-launch flags (see below).
- `deploy/scripts/` — `prod-app-flags.sh`, `render-prod-caddy.sh`, migration helpers.
- `infra/terraform/` — DigitalOcean Droplet + firewall.
- `.github/workflows/` — `ci.yml`, `deploy.yml`, droplet ops workflows.
- `docs/` — runbooks; `docs/README.md` is the documentation map.

## Common Commands

Sync and test all apps:

```bash
./scripts/sync-apps.sh --locked
./scripts/test-apps.sh
```

Per-app (use these when changing one app):

```bash
uv sync --project apps/<app>
uv run --project apps/<app> pytest apps/<app>/tests -q
```

App-specific exceptions:

- Prefect: `pytest apps/prefect/tests/property/` (property tests, not all of `tests/`).
- Flow: also run `uv run --project apps/flow python apps/flow/scripts/validate-dags.py`.

Compose validation (matches what CI runs):

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local config
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production.generated config
```

Local stack helper: `./scripts/local-compose.sh {config|up|ps|logs|down}`.

Pre-commit runs `isort` + `black` per app under `apps/<app>/` via `env -u VIRTUAL_ENV uv run --project apps/<app> --locked`. Match this invocation when running formatters manually.

## Architecture

Single DigitalOcean Droplet (`platform-shared`, `174.138.71.121`, `s-1vcpu-2gb`) runs Docker Compose in production. Caddy is the only public ingress on `80/443`; all app containers join one network (`platform-local` / `platform-prod`).

Production runs a **single shared Postgres** container (`platform-postgres`) with separate `prefect` and `airflow` databases/roles. Local Compose runs separate `prefect-postgres` and `airflow-postgres` containers. The consolidated production layout is what enables the small Droplet — don't reintroduce separate prod Postgres volumes (`prefect-postgres-data`, `airflow-postgres-data`) without an explicit ask.

Raman keeps agent state in its own Docker volume (`raman-state`). The former
Homi and Vikram apps are deprecated and no longer wired into shared Compose,
CI, deploy, or Caddy routes.

### Production app flags

`deploy/apps.prod.env` is the **only** place to enable/disable an app in production. The deploy workflow reads it via `deploy/scripts/prod-app-flags.sh` to:

1. Compute `COMPOSE_PROFILES` (disabled apps live behind Compose profiles, so their code/config/volumes stay intact but they don't start).
2. Render `deploy/caddy/prod-sites/` from templates via `deploy/scripts/render-prod-caddy.sh` (disabled hostnames return `404`).

Do **not** edit `COMPOSE_PROFILES` on the host or hand-edit `prod-sites/`. Change the flag file in a PR and let the deploy workflow render.

### Deploy

Pushes to `main` trigger `.github/workflows/deploy.yml`. The workflow temporarily allowlists the GitHub runner `/32` in the DigitalOcean firewall, SSH-deploys, force-recreates Caddy, runs public smoke checks, and removes the temporary SSH rule in an `always()` cleanup step. Do not replace this pattern with `0.0.0.0/0` SSH.

Manual redeploy: `gh workflow run deploy.yml --repo raniendu/platform --ref main`.

### Routing

Local hostnames: `dotdev.localhost`, `prefect.localhost`, `raman.localhost`, `flow.localhost`. Direct container ports (`8501`, `4200`, `8000`, `8080`, `16686`) are also exposed for smoke tests.

Production hostnames: `raniendu.dev` (DotDev), `prefect.raniendu.dev`, `raman.raniendu.dev`, `flow.raniendu.dev`, `jaeger.raniendu.dev`. `www.raniendu.dev` redirects to `https://raniendu.dev{uri}`. DNS is managed manually in Squarespace; apex must be an `A` record (not `ALIAS`).

## Critical Rules

- **Never** print, commit, or paste values from `.env.local`, `.env.production.generated`, `.env.production.credentials`, Terraform state, SSH keys, or GitHub secrets. If the user needs a value from `.env.production.credentials`, point them to read it locally.
- Caddy bcrypt hashes in Compose env files must escape `$` as `$$`.
- Local `doctl` is **read-only**. All DigitalOcean writes go through reviewed PRs + GitHub Actions. Do not run local `terraform apply` against production.
- Never push without an accompanying PR — a remote branch push is allowed only as the mechanical step to open/update a PR. Don't commit or push without an explicit user request.
- Don't change or delete old production resources (DigitalOcean inventory, volumes, snapshots, DNS records) without explicit per-step approval.
- Before claiming cost/inventory facts, query the DigitalOcean inventory (Droplets, App Platform, databases, volumes, load balancers, snapshots, firewalls) — don't infer from old docs.
- Google Maps integration is intentionally not implemented; do not reintroduce it.
- Keep app-specific logic inside its app directory; shared runtime/deploy work belongs under `deploy/`, `.github/workflows/`, `infra/`, or `docs/`.

## Raman local modes

Raman has two distinct local paths, which use different env files and different Ollama URLs:

- Repo-root Compose: uses root `.env.local` and `OLLAMA_BASE_URL=http://host.docker.internal:11434/v1`.
- Direct `uv` development from `apps/raman/`: uses `apps/raman/.env` and `OLLAMA_BASE_URL=http://localhost:11434/v1`.

## Verification

Before reporting done, run the narrowest useful checks for the changed area and state what passed. Touched workflows → check CI. Touched Compose → `docker compose ... config`. Touched Caddyfile → validate syntax. Touched Terraform → `plan` only; never apply.
