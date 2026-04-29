# Smaller Droplet Migration

The current `platform-shared` Droplet cannot be resized in place to `s-1vcpu-2gb` because it has an 80 GiB disk and `s-1vcpu-2gb` has a 50 GiB disk. DigitalOcean rejects that resize even with `resize_disk = true`.

All DigitalOcean write operations for this migration must run from GitHub Actions after review and approval. Local `doctl` usage is read-only.

## Preconditions

- Postgres consolidation has deployed successfully.
- Public smoke checks pass on the current Droplet.
- `PLATFORM_ENV_FILE` contains `PLATFORM_POSTGRES_PASSWORD`, `PREFECT_POSTGRES_PASSWORD`, and `AIRFLOW_POSTGRES_PASSWORD`.
- The current Droplet has a fresh backup or snapshot.
- A migration PR has been reviewed. Do not make routine `deploy.yml` create a second Droplet.

## Required Migration Shape

Use a dedicated manual workflow or one-off PR, not the normal deploy workflow:

1. Require a typed confirmation input, for example `migrate-platform-shared-to-s-1vcpu-2gb`.
2. Create a new `s-1vcpu-2gb` Droplet from GitHub Actions.
3. Bootstrap Docker with the existing cloud-init script.
4. Temporarily allowlist the GitHub runner `/32` on both the old and new Droplet firewalls.
5. Stop application writers on the old Droplet and dump the consolidated `prefect` and `airflow` databases from `platform-postgres`.
6. Upload the repository and production env file to the new Droplet.
7. Start `platform-postgres` on the new Droplet and restore both database dumps.
8. Start the production Compose stack on the new Droplet.
9. Verify container health over SSH before DNS cutover.
10. Update Squarespace DNS manually to the new Droplet IP.
11. Run public smoke checks.
12. Keep the old Droplet until explicit post-cutover approval to decommission it.

## Rollback

Before decommissioning the old Droplet, rollback is DNS-only:

1. Point Squarespace DNS records back to the old Droplet IP.
2. Run the production deploy workflow against the old Droplet state.
3. Verify public smoke checks: `200`, `301`, `401`, `200`.

After the old Droplet is decommissioned, rollback requires restoring from the latest backup or snapshot.
