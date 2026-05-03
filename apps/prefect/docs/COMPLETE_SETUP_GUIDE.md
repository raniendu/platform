# Prefect Production Setup

This app no longer has an independent production setup guide. The old standalone Prefect DigitalOcean Droplet, Nginx proxy, per-app Terraform state, and `DO_TOKEN`/`DO_SSH_*` secret model were retired during the platform consolidation.

Use this file as a Prefect-specific pointer into the current shared setup.

## Current Production Shape

- Repository: `raniendu/platform`
- Runtime host: DigitalOcean Droplet `platform-shared`
- Size: `s-1vcpu-2gb`
- Public route: `https://prefect.raniendu.dev`
- Reverse proxy: Caddy from `deploy/caddy/Caddyfile.prod`
- Compose file: `deploy/compose/docker-compose.prod.yml`
- Production metadata DB: `platform-postgres`, database `prefect`, role `prefect`
- Deployment workflow: `.github/workflows/deploy.yml`, manual `workflow_dispatch`

## Setup Checklist

Use the root platform docs for the authoritative steps:

1. Configure production GitHub environment secrets and variables from `docs/secrets.md`.
2. Put complete production app values in the `PLATFORM_ENV_FILE` GitHub secret.
3. Keep `PREFECT_POSTGRES_PASSWORD`, `PREFECT_BASIC_AUTH_USER`, `PREFECT_BASIC_AUTH_HASH`, `PUSHOVER_APP_TOKEN`, `PUSHOVER_USER_KEY`, and `GEMINI_API_KEY` in that env file when the corresponding feature is enabled.
4. Confirm Squarespace DNS points `prefect.raniendu.dev` at the current `platform-shared` Droplet IP.
5. Deploy with the root `Deploy` GitHub Actions workflow.

## Commands

Local development:

```bash
cp .env.example .env.local
uv sync --project apps/prefect
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build
```

Production deploy:

```bash
gh workflow run deploy.yml --repo raniendu/platform --ref main
gh run watch --repo raniendu/platform --exit-status
```

Expected Prefect smoke check:

```text
prefect.raniendu.dev/api/health -> 401
```

The `401` is expected because Caddy basic auth protects Prefect.

## Do Not Use Legacy Instructions

These legacy instructions are intentionally obsolete and should not be recreated in this app directory:

- app-local Terraform for Prefect;
- standalone `docker-compose.prod.yml` under `apps/prefect`;
- Nginx/certbot production proxy for Prefect;
- `prefect-server` Droplet;
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
