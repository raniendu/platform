# Smaller Droplet Migration

The current `platform-shared` Droplet cannot be resized in place to `s-1vcpu-2gb` because it has an 80 GiB disk and `s-1vcpu-2gb` has a 50 GiB disk. DigitalOcean rejects that resize even with `resize_disk = true`.

All DigitalOcean write operations for this migration must run from GitHub Actions after review and approval. Local `doctl` usage is read-only.

The migration workflow is `.github/workflows/migrate-smaller-droplet.yml`. It creates a temporary replacement Droplet named `platform-shared-small`, migrates data, waits for manual DNS cutover, promotes the small Droplet back to the canonical `platform-shared` name, and only deletes the old Droplet in a separate typed-confirmation phase.

## Preconditions

- Postgres consolidation has deployed successfully.
- Public smoke checks pass on the current Droplet.
- `PLATFORM_ENV_FILE` contains `PLATFORM_POSTGRES_PASSWORD`, `PREFECT_POSTGRES_PASSWORD`, and `AIRFLOW_POSTGRES_PASSWORD`.
- The current Droplet has a fresh backup or snapshot.
- The migration PR has been reviewed and merged. Do not make routine `deploy.yml` create a second Droplet.
- The GitHub `production` environment still requires human approval.

## Workflow Phases

Use the dedicated manual workflow, not the normal deploy workflow:

### 1. Stage

Run `Migrate Smaller Droplet` with:

- `phase`: `stage`
- `confirmation`: `stage-platform-shared-to-s-1vcpu-2gb`
- `retired_droplet_name`: blank

The stage phase:

1. Fails unless it is running inside GitHub Actions.
2. Creates `platform-shared-small` as `s-1vcpu-2gb`, or reuses exactly one existing Droplet with that name.
3. Attaches the new Droplet to `platform-shared-firewall`.
4. Temporarily allowlists the GitHub runner `/32` for SSH.
5. Builds SHA-pinned production images and pushes them to GHCR.
6. Uploads the repository and `PLATFORM_ENV_FILE` to the new Droplet.
7. Stops any runtime containers already present on a reused staging Droplet before restoring databases.
8. Verifies the old Droplet already has the consolidated `platform-postgres` container.
9. Stops old Prefect/Airflow writers on `platform-shared` to avoid post-dump divergence.
10. Dumps the consolidated `prefect` and `airflow` databases from `platform-postgres`.
11. Copies Caddy certificate/config volumes so HTTPS can be smoke-tested before DNS cutover.
12. Restores Postgres dumps on the new Droplet with each database's objects restored as its application role (`prefect` or `airflow`), so the services can run migrations and health checks without table-permission failures.
13. Starts the staged Compose stack in phases: DotDev first, then the one-shot Airflow database init, then Prefect/Airflow runtime services and Caddy. This avoids a high-memory parallel startup on the 2 GiB Droplet.
14. Checks the `platform-airflow-init` exit code explicitly and prints the last logs if Airflow init fails, then restarts the old production stack during cleanup.
15. Runs container health checks and `curl --resolve` public-route smoke checks against the new IP.
16. Leaves old Prefect/Airflow writers stopped after success.

The workflow summary prints the new Droplet IP. Use that IP for the Squarespace A records.

### 2. DNS Cutover

Manually update Squarespace A records to the staged Droplet IP:

- `raniendu.dev`
- `prefect.raniendu.dev`
- `flow.raniendu.dev`

Keep `www.raniendu.dev` pointed according to the existing redirect setup.

### 3. Promote

After DNS resolves to the new Droplet and public smoke checks pass, run `Migrate Smaller Droplet` with:

- `phase`: `promote`
- `confirmation`: `promote-platform-shared-small-to-platform-shared`
- `retired_droplet_name`: blank

The promote phase verifies that the old writer containers are still stopped, verifies that `https://raniendu.dev/` reaches the staged Droplet IP, runs public smoke checks, renames the old Droplet to `platform-shared-retired-<run-id>`, and renames `platform-shared-small` to `platform-shared`. This restores the canonical name that routine deploys adopt.

### 4. Decommission

After the small Droplet has been accepted in production, run `Migrate Smaller Droplet` with:

- `phase`: `decommission_retired`
- `confirmation`: `decommission-<retired-droplet-name>`
- `retired_droplet_name`: `<retired-droplet-name>` from the promote workflow summary

The decommission phase verifies the canonical `platform-shared` Droplet is `s-1vcpu-2gb`, runs public smoke checks, detaches the retired Droplet from the firewall, then deletes the retired Droplet. This is the step that reduces steady-state Droplet cost.

## Routine Deploy Safety

The normal `Deploy` workflow refuses to run while a Droplet named `platform-shared-small` exists. Finish `promote` or run `rollback_stage` before using routine deploys again.

For migration recovery only, `Deploy` has an `allow_migration_staging_host` input. Use it when a failed stage created `platform-shared-small` before Postgres consolidation reached the old Droplet, so consolidation can be deployed before retrying `stage`.

Terraform's desired size is now `s-1vcpu-2gb`, but the Droplet resource ignores `size` drift. That prevents routine deploys from trying the impossible in-place disk shrink on the existing 80 GiB Droplet while still creating a small Droplet if a brand-new environment is ever bootstrapped from empty inventory.

## Rollback

Before `promote`, rollback is DNS-first:

1. Point Squarespace DNS records back to the old Droplet IP shown in the stage summary.
2. Run `Migrate Smaller Droplet` with:
   - `phase`: `rollback_stage`
   - `confirmation`: `rollback-platform-shared-small`
   - `retired_droplet_name`: blank
3. Verify public smoke checks: `200`, `301`, `401`, `200`.

After `promote` but before `decommission_retired`, the old Droplet still exists as `platform-shared-retired-<run-id>`, but rollback is no longer DNS-only because the canonical resource names have changed. Prefer validating the staged host before `promote`.

After the old Droplet is decommissioned, rollback requires restoring from the latest backup or snapshot.
