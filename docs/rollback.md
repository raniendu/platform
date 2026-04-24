# Rollback

Old DigitalOcean and App Platform resources stay live until the new public endpoints are verified and decommissioning is explicitly approved.

## Before DNS Cutover

If local or production verification fails before DNS changes, leave Squarespace records pointing at the old services. Stop or fix the new stack without touching old resources.

## After DNS Cutover

If the new Droplet fails after DNS changes:

1. Repoint Squarespace A records to the previous known-good targets.
2. Keep the new Droplet running for log inspection unless it is causing harm.
3. Verify `raniendu.dev`, `prefect.raniendu.dev`, and `flow.raniendu.dev` against the old services.
4. Fix the new stack and repeat public verification before trying another cutover.

## Data Considerations

Prefect starts fresh; historical runs and blocks are not migrated. Airflow DAG code is migrated, but old Airflow runtime state is not relied on by this bootstrap.

## Decommissioning Gate

Delete old resources only after explicit approval for each target:

- old Prefect Droplet,
- old Airflow Terraform resources and state cleanup,
- `dot-dev-app` App Platform app.

