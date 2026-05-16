# Rollback

Rollback now assumes the consolidated `platform-shared` Droplet is the only active production host for DotDev, Prefect, Raman, and Airflow. The old App Platform app, old Prefect Droplet, and retired 4 GiB platform Droplet have already been deleted.

## Before DNS Cutover

If a future replacement host is staged and verification fails before DNS changes, leave Squarespace records pointing at the current `platform-shared` host. Stop or fix the staged stack without touching the current host.

## After DNS Cutover

If a future replacement Droplet fails after DNS changes:

1. Repoint Squarespace A records to the previous known-good `platform-shared` IP if that Droplet still exists.
2. Keep the new Droplet running for log inspection unless it is causing harm.
3. Verify `raniendu.dev`, `prefect.raniendu.dev`, `raman.raniendu.dev`, and `flow.raniendu.dev` against the restored target.
4. Fix the new stack and repeat public verification before trying another cutover.

## Data Considerations

Production currently uses one shared Postgres container with separate `prefect` and `airflow` databases. Raman thread history plus DBOS workflow state use `raman-state`. After the old 4 GiB Droplet was decommissioned, rollback requires restoring from the latest Droplet backup/snapshot or app-level database backup.

## Decommissioning Gate

Delete any future replacement or retired resources only after explicit approval for each target. Local DigitalOcean CLI usage is read-only only; approved infrastructure writes should run through GitHub Actions.
