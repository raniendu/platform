# Deployment

Production deploys are manual GitHub Actions runs that update the shared DigitalOcean Droplet at `/opt/platform`.

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
- `deploy.yml`: manual `workflow_dispatch` deploy to the shared Droplet.

Expected deploy workflow:

1. Add the current GitHub runner `/32` to the DigitalOcean firewall for SSH.
2. Upload repository files to `/opt/platform`.
3. Upload the production env file to `/opt/platform/.env.production`.
4. Run `docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production up -d --build`.
5. Force-recreate Caddy so file-bound Caddyfile changes are picked up.
6. Smoke test the public endpoints.
7. Remove the temporary GitHub runner SSH firewall rule in an `always()` cleanup step.

GitHub secrets are listed in `docs/secrets.md`. Do not run `Deploy` until Terraform has created the Droplet and production secrets are configured.

## Gate 4: Terraform Apply

Terraform is under `infra/terraform`.

```bash
cd infra/terraform
terraform init
terraform plan -var-file=terraform.tfvars
```

Show the plan and get explicit approval before `terraform apply`. The initial Droplet size is `s-2vcpu-4gb`.

## Production Host Bootstrap

Cloud-init installs Docker and creates `/opt/platform`. After the Droplet exists, deployment should copy this repository to `/opt/platform`, create a root-only production env file, and start production Compose.

```bash
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production up -d --build
```

Public verification waits until Squarespace DNS cutover is complete.

## Manual Deploy Preconditions

Before running the `Deploy` workflow:

- GitHub environment `production` exists and requires approval.
- `PLATFORM_SSH_HOST` points at the new shared Droplet.
- `DIGITALOCEAN_ACCESS_TOKEN` is set in the GitHub environment so the workflow can add and remove its temporary SSH firewall rule.
- `PLATFORM_FIREWALL_ID` is set as a GitHub environment variable for the DigitalOcean firewall attached to the Droplet.
- `PLATFORM_ENV_FILE` contains the complete production `.env.production` content.
- `/opt/platform` exists on the Droplet. Cloud-init creates it for the Terraform-managed Droplet.
- The DigitalOcean firewall allows SSH from the deploy runner. The GitHub workflow adds the runner's current `/32` IP before SSH and removes it in an `always()` cleanup step. Keep Terraform `allowed_ssh_cidrs` restricted to stable administrator IPs rather than opening SSH globally.

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
