# Deployment

Deployment is intentionally blocked until the local verification gate passes.

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

1. Run app sync and targeted tests.
2. Build Docker images or build on the Droplet during deploy.
3. Deploy Compose files to `/opt/platform`.
4. Run `docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production up -d --build`.

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
