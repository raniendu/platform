# Airflow Production Setup

This app no longer has an independent production setup guide. The old standalone Airflow DigitalOcean Droplet, Nginx proxy, per-app Terraform state, Spaces backend, and `infra_enabled` pause/resume model were retired during the platform consolidation.

Use this file as an Airflow-specific pointer into the current shared setup.

## Current Production Shape

- Repository: `raniendu/platform`
- Runtime host: DigitalOcean Droplet `platform-shared`
- Size: `s-1vcpu-2gb`
- Public route: `https://flow.raniendu.dev`
- Reverse proxy: Caddy from `deploy/caddy/Caddyfile.prod`
- Compose file: `deploy/compose/docker-compose.prod.yml`
- Production metadata DB: `platform-postgres`, database `airflow`, role `airflow`
- Deployment workflow: `.github/workflows/deploy.yml`, manual `workflow_dispatch`

## Setup Checklist

Use the root platform docs for the authoritative steps:

1. Configure production GitHub environment secrets and variables from `docs/secrets.md`.
2. Put complete production app values in the `PLATFORM_ENV_FILE` GitHub secret.
3. Keep `AIRFLOW_POSTGRES_PASSWORD`, `AIRFLOW__CORE__FERNET_KEY`, `AIRFLOW__WEBSERVER__SECRET_KEY`, `AIRFLOW_ADMIN_USER`, and `AIRFLOW_ADMIN_PASSWORD` in that env file.
4. Confirm Squarespace DNS points `flow.raniendu.dev` at the current `platform-shared` Droplet IP.
5. Deploy with the root `Deploy` GitHub Actions workflow.

## Commands

Local development:

```bash
cp .env.example .env.local
uv sync --project apps/flow
uv run --project apps/flow python apps/flow/scripts/validate-dags.py
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build
```

Production deploy:

```bash
gh workflow run deploy.yml --repo raniendu/platform --ref main
gh run watch --repo raniendu/platform --exit-status
```

Expected Airflow smoke check:

```text
flow.raniendu.dev -> 200
```

## Do Not Use Legacy Instructions

These legacy instructions are intentionally obsolete and should not be recreated in this app directory:

- standalone `terraform/` for Airflow;
- `terraform/deployment.auto.tfvars` or `infra_enabled`;
- standalone `docker-compose.yml` production stack under `apps/flow`;
- Nginx/certbot production proxy for Airflow;
- `airflow-server` Droplet;
- Spaces backend setup for app-specific Terraform state;
- `DO_TOKEN`, `DO_SSH_PRIVATE_KEY`, or `DO_SSH_KEY_FINGERPRINT` app-specific secrets;
- automatic deployment just by pushing to `main`.

For infrastructure changes, open a reviewed PR and let GitHub Actions perform the approved write operations. Local DigitalOcean CLI usage is read-only only.

## References

- `docs/deployment.md`
- `docs/developer-guide.md`
- `docs/secrets.md`
- `docs/operations.md`
- `docs/rollback.md`
- `docs/digitalocean-cost-comparison.md`
