# Deployment

Production deploys are manual GitHub Actions runs that apply the shared DigitalOcean infrastructure and then update the Droplet at `/opt/platform`.

Current production host:

- Droplet: `platform-shared`
- IP: `174.138.71.121`
- Size: `s-1vcpu-2gb`
- Firewall: `platform-shared-firewall`
- Estimated steady-state cost with weekly backups: about `$14.40/month`

Current production routes:

- `https://raniendu.dev` -> DotDev
- `https://prefect.raniendu.dev` -> Prefect behind Caddy basic auth
- `https://raman.raniendu.dev` -> Raman agent health and Telegram webhook endpoint
- `https://homi.raniendu.dev` -> Homi only when DNS exists and `DEPLOY_HOMI=true`
- `https://vikram.raniendu.dev` -> Vikram only when DNS exists and `DEPLOY_VIKRAM=true`
- `https://paperclip.raniendu.dev` -> disabled by `deploy/apps.prod.env`, returns `404`
- `https://flow.raniendu.dev` -> disabled by `deploy/apps.prod.env`, returns `404`

Production app launch is controlled by tracked flags in `deploy/apps.prod.env`. Keep app code, config, secrets, databases, and volumes in place; change only these flags and rerun `Deploy` to start or stop a production app:

```env
DEPLOY_DOTDEV=true
DEPLOY_PREFECT=true
DEPLOY_FLOW=false
DEPLOY_PAPERCLIP=false
DEPLOY_RAMAN=true
DEPLOY_HOMI=false
DEPLOY_VIKRAM=false
```

The initial local, GitHub, Terraform, and DNS gates have passed. Keep the gate notes below for rebuilds or disaster recovery.

## Gate 1: Local Build Approval

Before any GitHub or DigitalOcean change, prove:

- all app `uv sync` commands complete,
- targeted app tests pass,
- local Compose config renders,
- local Compose builds and starts,
- Caddy routes all local hostnames,
- smoke tests show DotDev, Raman, Homi, Vikram, Prefect, Paperclip, and Airflow are reachable.

## Gate 2: GitHub Repo Creation

Default repo name: `raniendu/platform`.

After approval, create the GitHub repo manually or with `gh`, then add the remote. Do not push local secrets or `.env.local`.

## Gate 3: GitHub Actions And Secrets

CI/deploy workflows are under `.github/workflows/`.

- `ci.yml`: runs per-app `uv sync`, targeted tests, Airflow DAG validation, and Compose config validation.
- `deploy.yml`: manual `workflow_dispatch` infrastructure apply and deploy to the shared Droplet.
- `migrate-smaller-droplet.yml`: manual, typed-confirmation migration workflow used for the completed May 2026 move from the old 80 GiB `s-2vcpu-4gb` Droplet to the current 50 GiB `s-1vcpu-2gb` Droplet. Keep it as a migration/recovery runbook, not as the routine deploy path.

Expected deploy workflow:

1. Read `deploy/apps.prod.env`, build enabled in-repo app images in GitHub Actions, and push them to GHCR with the current commit SHA tag.
2. After the GitHub `production` environment approval, query DigitalOcean for `platform-shared` and `platform-shared-firewall`; the deploy stops if inventory cannot be read.
3. Import exactly one existing matching Droplet/firewall into Terraform state, fail if duplicates exist, fail if the smaller-Droplet staging host `platform-shared-small` exists, or allow Terraform to create one Droplet if none exists.
4. Plan and apply Terraform from `infra/terraform`; the guard refuses any Droplet delete/replace and refuses creating a second Droplet when one already exists.
5. Add the current GitHub runner `/32` to the Terraform-managed DigitalOcean firewall for SSH.
6. Upload repository files to `/opt/platform`.
7. Upload the production env file to `/opt/platform/.env.production`, appending deploy flags and SHA-pinned image references, including agent images such as `RAMAN_IMAGE=ghcr.io/raniendu/platform/raman:<sha>`.
8. Upload temporary GHCR credentials, render the enabled/disabled production Caddy routes, stop disabled app containers without deleting volumes, and pull enabled images on the Droplet.
9. Run the one-time Postgres consolidation if the host still has separate Prefect and Airflow Postgres containers.
10. Run the idempotent Paperclip database initializer only when Paperclip is enabled so existing `platform-postgres` volumes get the `paperclip` role and database.
11. Run production Compose with `COMPOSE_PROFILES` matching the enabled app flags and `up -d --no-build`.
12. Force-recreate Caddy so file-bound Caddyfile changes are picked up.
13. Smoke test the public endpoints, including agent `/healthz` routes when enabled, then stop the legacy Prefect/Airflow Postgres containers if the smoke checks pass.
14. Remove temporary GHCR credentials and the GitHub runner SSH firewall rule in `always()` cleanup steps.

GitHub secrets are listed in `docs/secrets.md`. Do not run `Deploy` until production secrets are configured.

## Gate 4: Terraform Apply

Terraform is under `infra/terraform`.

```bash
cd infra/terraform
terraform init
terraform plan -var-file=terraform.tfvars
```

Normal production applies run through `deploy.yml` after the GitHub `production` environment approval. Terraform's desired size is `s-1vcpu-2gb` with DigitalOcean monitoring and weekly backups enabled. The Droplet resource still protects against destructive replacement and imports the existing `platform-shared` Droplet before applying so a missing GitHub-side state file does not create a duplicate Droplet.

## Production Host Bootstrap

Cloud-init installs Docker and creates `/opt/platform`. After the Droplet exists, deployment should copy this repository to `/opt/platform`, create a root-only production env file, pull the SHA-pinned GHCR images, and start production Compose.

```bash
bash deploy/scripts/render-prod-caddy.sh deploy/apps.prod.env deploy/caddy/prod-sites
COMPOSE_PROFILES=dotdev,prefect,raman docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production pull postgres caddy dotdev prefect-server prefect-worker raman
COMPOSE_PROFILES=dotdev,prefect,raman docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production up -d --no-build
```

Public verification waits until Squarespace DNS cutover is complete.

## Manual Deploy Preconditions

Before running the `Deploy` workflow:

- GitHub environment `production` exists and requires approval.
- `DIGITALOCEAN_ACCESS_TOKEN` is set in the GitHub environment so the workflow can add and remove its temporary SSH firewall rule.
- `DO_SSH_KEY_FINGERPRINTS` is set as a GitHub environment variable or secret using Terraform list syntax, for example `["aa:bb:cc"]`.
- `ALLOWED_SSH_CIDRS` is set as a GitHub environment variable or secret using Terraform list syntax, for example `["203.0.113.10/32"]` or `[]`.
- `PLATFORM_ENV_FILE` contains the shared production `.env.production` content.
- `PLATFORM_ENV_FILE` includes `PLATFORM_POSTGRES_PASSWORD`, `PREFECT_POSTGRES_PASSWORD`, `AIRFLOW_POSTGRES_PASSWORD`, and `PAPERCLIP_POSTGRES_PASSWORD`; the deploy workflow validates additional app auth keys only when their app flag is enabled.
- When `DEPLOY_RAMAN=true`, the GitHub `production` environment includes `DO_INFERENCE_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, and `TELEGRAM_ALLOWED_CHAT_IDS` secrets. `PARALLEL_API_KEY` is optional unless Raman enables web search.
- When `DEPLOY_HOMI=true`, configure `HOMI_TELEGRAM_BOT_TOKEN`, `HOMI_TELEGRAM_WEBHOOK_SECRET`, `HOMI_TELEGRAM_ALLOWED_CHAT_IDS`, and Bedrock credentials through `AWS_BEARER_TOKEN_BEDROCK` or the standard AWS access key pair. `HOMI_PARALLEL_API_KEY` is optional unless Homi enables web search.
- When `DEPLOY_VIKRAM=true`, configure `GOOGLE_API_KEY`, `VIKRAM_TELEGRAM_BOT_TOKEN`, `VIKRAM_TELEGRAM_WEBHOOK_SECRET`, and `VIKRAM_TELEGRAM_ALLOWED_CHAT_IDS`. `VIKRAM_PARALLEL_API_KEY` is optional unless Vikram enables web search.
- `DO_INFERENCE_API_KEY` should be a DigitalOcean model access key scoped to `gemma-4-31B-it` for the production Raman deployment. Serverless inference does not require a Terraform-managed endpoint or dedicated GPU resource.
- The deploy workflow appends `DOTDEV_IMAGE`, `PREFECT_IMAGE`, `AIRFLOW_IMAGE`, `PAPERCLIP_IMAGE`, `RAMAN_IMAGE`, `HOMI_IMAGE`, and `VIKRAM_IMAGE`; these do not need to be stored in `PLATFORM_ENV_FILE`.
- The deploy workflow appends `DEPLOY_DOTDEV`, `DEPLOY_PREFECT`, `DEPLOY_FLOW`, `DEPLOY_PAPERCLIP`, `DEPLOY_RAMAN`, `DEPLOY_HOMI`, and `DEPLOY_VIKRAM`; these are tracked in `deploy/apps.prod.env`, not stored as GitHub secrets.
- The deploy workflow appends Raman's production constants (`RAMAN_MODEL_PROVIDER=digitalocean`, `RAMAN_DEV_MODEL=gemma-4-31B-it`, `RAMAN_AGENT=raman`, and `RAMAN_PUBLIC_BASE_URL=https://raman.raniendu.dev`) plus the Raman GitHub secrets to the host env file at deploy time.
- The deploy workflow appends Homi and Vikram production constants and their app-specific secrets only when their deploy flags are enabled.
- Cloud-init creates `/opt/platform` for a new Terraform-managed Droplet, and the deploy workflow waits for bootstrap before uploading files.
- The DigitalOcean firewall allows SSH from the deploy runner. The GitHub workflow adds the runner's current `/32` IP before SSH and removes it in an `always()` cleanup step. Keep Terraform `allowed_ssh_cidrs` restricted to stable administrator IPs rather than opening SSH globally.

If Terraform creates a new environment because no `platform-shared` Droplet exists, update Squarespace DNS to the new `droplet_ip` output before relying on the public smoke checks. App subdomains such as `paperclip`, `raman`, `homi`, and `vikram` require `A` records pointing at the Droplet IP before their public smoke checks can pass.

## Smaller Droplet Migration

The smaller-Droplet migration completed on 2026-05-02. Production now runs on `platform-shared` at `174.138.71.121` with size `s-1vcpu-2gb`, and the retired 4 GiB Droplet was deleted by the `decommission_retired` phase.

Keep this workflow documented because it is the audited pattern for future new-Droplet migrations. Use `Deploy`, not `Migrate Smaller Droplet`, for routine production releases.

The workflow has four manual phases:

| Phase | Typed confirmation | Purpose |
| --- | --- | --- |
| `stage` | `stage-platform-shared-to-s-1vcpu-2gb` | Create or reuse one `platform-shared-small` Droplet, migrate Postgres and Caddy data, deploy the stack, and smoke-test the new IP with `curl --resolve`. |
| `promote` | `promote-platform-shared-small-to-platform-shared` | After Squarespace DNS points at the new IP, verify public smoke checks and rename the small Droplet back to canonical `platform-shared`. |
| `rollback_stage` | `rollback-platform-shared-small` | Stop staged writers and restart the old canonical stack if the cutover is abandoned before promotion. |
| `decommission_retired` | `decommission-<retired-droplet-name>` | After acceptance, delete the retired old Droplet. This is the cost-reduction step. |

Routine deploys refuse to run while `platform-shared-small` exists, because that name means a future migration is staged but not promoted or rolled back.

If a failed stage created `platform-shared-small` before Postgres consolidation was deployed, run `Deploy` with `allow_migration_staging_host=true` to deploy consolidation to the old canonical Droplet. Use this only for migration recovery; routine deploys should keep the default `false`.

## Manual Redeploy

From this repository:

```bash
gh workflow run deploy.yml --repo raniendu/platform --ref main
gh run watch --repo raniendu/platform --exit-status
```

Raman, Homi, and Vikram are built from their app directories during the `Deploy` workflow when their deploy flags are enabled. Rollbacks should redeploy a prior platform commit so all app image refs and deployment wiring stay in sync.

The workflow is expected to report these smoke statuses:

- `raniendu.dev` -> `200`
- `www.raniendu.dev` -> `301`
- `prefect.raniendu.dev/api/health` -> `401`
- `raman.raniendu.dev/healthz` -> `200`
- `paperclip.raniendu.dev` -> `404`
- `flow.raniendu.dev` -> `404`

`401` for Prefect is expected because Caddy basic auth is protecting that route. Paperclip and Flow return `404` while their production app flags are disabled. Homi and Vikram are skipped while disabled so routine Raman deploys do not require their DNS records.

The production browser credentials for the Paperclip Caddy prompt live in `.env.production.credentials` as `PAPERCLIP_BASIC_AUTH_USER` and `PAPERCLIP_BASIC_AUTH_PASSWORD`. The deploy env file and GitHub `PLATFORM_ENV_FILE` use `PAPERCLIP_BASIC_AUTH_HASH`; do not try to sign in with `PAPERCLIP_BETTER_AUTH_SECRET`, which is only an internal Paperclip auth/session secret.

## Postgres Consolidation

Production now uses one shared Postgres container, `platform-postgres`, with separate `prefect`, `airflow`, and `paperclip` databases and roles. Local development still uses separate local Postgres containers.

On the first deploy to an existing host, `deploy/scripts/consolidate-postgres.sh`:

1. Stops Prefect and Airflow application containers to avoid writes during dumps.
2. Dumps `platform-prefect-postgres` and `platform-airflow-postgres`.
3. Starts `platform-postgres`, whose init script creates the `prefect`, `airflow`, and `paperclip` roles/databases on fresh volumes.
4. Restores both dumps into the shared Postgres container.
5. Writes a marker at `/var/lib/platform/postgres-consolidated`.

If no legacy Postgres containers exist and `platform-postgres` already exists without the marker, the script starts that container, verifies the `postgres`, `prefect`, and `airflow` databases respond, and writes an `adopted` marker. This covers restored or migrated hosts where the shared database is already the steady state.

Existing initialized Postgres volumes do not rerun entrypoint init scripts, so the deploy workflow also runs `paperclip-db-init` before Paperclip starts. That one-shot container is idempotent and only ensures the `paperclip` role/database exist with the configured password.

The dump backups remain on the host under `/var/backups/platform/postgres-consolidation/` when the consolidation path runs. The smaller-Droplet migration has been accepted and the old 4 GiB host was decommissioned, so rollback now depends on Droplet backups/snapshots or app-level database backups rather than the old legacy Postgres containers.

## Paperclip First Admin

Generate the first Paperclip admin invite only after the service is running. Run the bootstrap command manually on the host or locally inside the container; do not add it to GitHub Actions because the invite URL is a credential.

```bash
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production exec paperclip pnpm paperclipai auth bootstrap-ceo --config /etc/paperclip/config.json --base-url https://paperclip.raniendu.dev
```
