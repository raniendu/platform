# Deployment

Production deploys are manual GitHub Actions runs that apply the shared DigitalOcean infrastructure and then update the Droplet at `/opt/platform`.

Current production routes:

- `https://raniendu.dev` -> DotDev
- `https://prefect.raniendu.dev` -> Prefect behind Caddy basic auth
- `https://flow.raniendu.dev` -> Airflow

The initial local, GitHub, Terraform, and DNS gates have passed. Keep the gate notes below for rebuilds or disaster recovery.

## Gate 1: Local Build Approval

Before any GitHub or DigitalOcean change, prove:

- all app `uv sync` commands complete,
- targeted app tests pass,
- local Compose config renders,
- local Compose builds and starts,
- Caddy routes all three local hostnames,
- smoke tests show DotDev, Prefect, and Airflow are reachable.

## Gate 2: GitHub Repo Creation

Default repo name: `raniendu/platform`.

After approval, create the GitHub repo manually or with `gh`, then add the remote. Do not push local secrets or `.env.local`.

## Gate 3: GitHub Actions And Secrets

CI/deploy workflows are under `.github/workflows/`.

- `ci.yml`: runs per-app `uv sync`, targeted tests, Airflow DAG validation, and Compose config validation.
- `deploy.yml`: manual `workflow_dispatch` infrastructure apply and deploy to the shared Droplet.

Expected deploy workflow:

1. Build DotDev, Prefect, and Airflow images in GitHub Actions and push them to GHCR with the current commit SHA tag.
2. After the GitHub `production` environment approval, query DigitalOcean for `platform-shared` and `platform-shared-firewall`.
3. Import exactly one existing matching Droplet/firewall into Terraform state, fail if duplicates exist, or allow Terraform to create one Droplet if none exists.
4. Plan and apply Terraform from `infra/terraform`; the guard refuses any Droplet delete/replace and refuses creating a second Droplet when one already exists.
5. Add the current GitHub runner `/32` to the Terraform-managed DigitalOcean firewall for SSH.
6. Upload repository files to `/opt/platform`.
7. Upload the production env file to `/opt/platform/.env.production`, appending the SHA-pinned image references for the deploy.
8. Upload temporary GHCR credentials, pull images on the Droplet, and run production Compose with `up -d --no-build`.
9. Force-recreate Caddy so file-bound Caddyfile changes are picked up.
10. Smoke test the public endpoints.
11. Remove temporary GHCR credentials and the GitHub runner SSH firewall rule in `always()` cleanup steps.

GitHub secrets are listed in `docs/secrets.md`. Do not run `Deploy` until production secrets are configured.

## Gate 4: Terraform Apply

Terraform is under `infra/terraform`.

```bash
cd infra/terraform
terraform init
terraform plan -var-file=terraform.tfvars
```

Normal production applies run through `deploy.yml` after the GitHub `production` environment approval. The target Droplet size is `s-1vcpu-2gb`.

## Production Host Bootstrap

Cloud-init installs Docker and creates `/opt/platform`. After the Droplet exists, deployment should copy this repository to `/opt/platform`, create a root-only production env file, pull the SHA-pinned GHCR images, and start production Compose.

```bash
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production pull dotdev prefect-server prefect-worker airflow-init airflow-webserver airflow-scheduler
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production up -d --no-build
```

Public verification waits until Squarespace DNS cutover is complete.

## Manual Deploy Preconditions

Before running the `Deploy` workflow:

- GitHub environment `production` exists and requires approval.
- `DIGITALOCEAN_ACCESS_TOKEN` is set in the GitHub environment so the workflow can add and remove its temporary SSH firewall rule.
- `DO_SSH_KEY_FINGERPRINTS` is set as a GitHub environment variable or secret using Terraform list syntax, for example `["aa:bb:cc"]`.
- `ALLOWED_SSH_CIDRS` is set as a GitHub environment variable or secret using Terraform list syntax, for example `["203.0.113.10/32"]` or `[]`.
- `PLATFORM_ENV_FILE` contains the complete production `.env.production` content.
- The deploy workflow appends `DOTDEV_IMAGE`, `PREFECT_IMAGE`, and `AIRFLOW_IMAGE`; these do not need to be stored in `PLATFORM_ENV_FILE`.
- Cloud-init creates `/opt/platform` for a new Terraform-managed Droplet, and the deploy workflow waits for bootstrap before uploading files.
- The DigitalOcean firewall allows SSH from the deploy runner. The GitHub workflow adds the runner's current `/32` IP before SSH and removes it in an `always()` cleanup step. Keep Terraform `allowed_ssh_cidrs` restricted to stable administrator IPs rather than opening SSH globally.

If Terraform creates a replacement environment because no `platform-shared` Droplet exists, update Squarespace DNS to the new `droplet_ip` output before relying on the public smoke checks.

## Manual Redeploy

From this repository:

```bash
gh workflow run deploy.yml --repo raniendu/platform --ref main
gh run watch --repo raniendu/platform --exit-status
```

The workflow is expected to report these smoke statuses:

- `raniendu.dev` -> `200`
- `www.raniendu.dev` -> `301`
- `prefect.raniendu.dev/api/health` -> `401`
- `flow.raniendu.dev` -> `200`

`401` for Prefect is expected because Caddy basic auth is protecting the route before the API health endpoint is reached.
