# Old Infrastructure Deprecation Plan

This plan removes old DigitalOcean resources after the consolidated platform has proven stable. Do not delete anything without explicit approval for that resource.

## Current Replacement

The consolidated platform is:

- Droplet: `platform-shared` at `174.138.59.96`
- Firewall: `platform-shared-firewall`
- Public routes:
  - `https://raniendu.dev`
  - `https://www.raniendu.dev` -> redirect to `https://raniendu.dev`
  - `https://prefect.raniendu.dev`
  - `https://flow.raniendu.dev`

## Preconditions

Complete these before deleting old infrastructure:

1. Latest GitHub `Deploy` workflow completed successfully.
2. Public smoke checks pass:

   ```bash
   curl -sS -o /dev/null -w '%{http_code}\n' https://raniendu.dev/
   curl -sS -o /dev/null -w '%{http_code}\n' https://www.raniendu.dev/
   curl -sS -o /dev/null -w '%{http_code}\n' https://prefect.raniendu.dev/api/health
   curl -sS -o /dev/null -w '%{http_code}\n' https://flow.raniendu.dev/
   ```

   Expected: `200`, `301`, `401`, `200`.

3. Squarespace DNS points only to the consolidated Droplet for `@`, `prefect`, and `flow`, with `www` as a CNAME to `raniendu.dev`.
4. Run at least one scheduled Prefect flow and confirm the worker handles it.
5. Confirm Airflow scheduler is running and visible in the UI.
6. Keep the new Droplet weekly backup enabled.
7. Decide whether to preserve old runtime data. The migration intentionally starts Prefect fresh and does not rely on old Airflow runtime state.

## Resource Inventory

Observed old resources:

| Resource | Current state | Decommission action |
| --- | --- | --- |
| Droplet `prefect-server` | active | Snapshot if rollback data is desired, then destroy |
| App Platform `dot-dev-app` | active | Remove old custom domains if still attached, then destroy the app |
| Old Airflow Terraform stack | no active Droplet observed | Confirm `terraform plan` with `infra_enabled=false`, then archive state/repo notes |

No old DigitalOcean managed databases, volumes, load balancers, or snapshots were observed.

## Step 1: Freeze Old Deploy Paths

Before deleting resources, stop old repos from silently redeploying:

- Disable or archive old deploy workflows in `dotDev`, `prefect`, and `flow`.
- Remove App Platform auto-deploy from `dot-dev-app` if deletion is delayed.
- Leave old repos readable for history, but make the `platform` repo the source of truth.

## Step 2: Deprecate DotDev App Platform

Target: `dot-dev-app`.

Checks:

```bash
doctl apps list
curl -I https://raniendu.dev/
curl -I https://www.raniendu.dev/
```

Plan:

1. Confirm `raniendu.dev` and `www.raniendu.dev` resolve to `174.138.59.96`.
2. Export or screenshot the App Platform spec if a record is wanted.
3. Remove custom domains from the old app if deletion is delayed.
4. After explicit approval, destroy `dot-dev-app`.
5. Re-run public smoke checks against the consolidated platform.

Rollback:

- Recreate the app from the old `dotDev` repo and point DNS back only if the consolidated DotDev route fails and cannot be fixed quickly.

## Step 3: Deprecate Old Prefect Droplet

Target: `prefect-server`.

Checks:

```bash
doctl compute droplet list
curl -I https://prefect.raniendu.dev/
```

Plan:

1. Confirm `prefect.raniendu.dev` resolves to `174.138.59.96`.
2. Confirm the new Prefect worker is polling the expected pool and a scheduled run completes.
3. If old run history or logs matter, take a manual snapshot before deletion. If not, skip the snapshot to avoid creating another billable artifact.
4. After explicit approval, destroy the old `prefect-server` Droplet.
5. Delete old Prefect firewall resources if any remain attached only to that Droplet.
6. Re-run Prefect public and worker checks.

Rollback:

- If a snapshot was taken, recreate the old Droplet from the snapshot and repoint DNS to its IP.
- If no snapshot was taken, rollback is through the old repo plus fresh Terraform apply.

## Step 4: Retire Old Airflow Terraform State

Target: old `flow` Terraform stack.

Checks:

```bash
cd /Users/raniendu/PycharmProjects/flow/terraform
terraform init
terraform plan
```

Expected state:

- `infra_enabled = false`
- no active `airflow-server` Droplet in `doctl compute droplet list`
- no `flow.raniendu.dev` DNS dependency in DigitalOcean DNS

Plan:

1. Confirm the old state has no managed resources or shows a destroy plan only for resources already replaced.
2. If Terraform still tracks old resources, show the plan and get explicit approval before applying.
3. Archive the old Terraform state location and note that `platform/infra/terraform` is now authoritative for shared runtime infrastructure.

Rollback:

- Re-enable the old `flow` Terraform stack only if the consolidated Airflow service cannot be recovered and the user approves a temporary split.

## Step 5: Clean GitHub And Secrets

After old infrastructure is deleted:

- Remove unused old GitHub secrets from old repos.
- Disable old deploy workflows.
- Keep `raniendu/platform` production secrets unchanged.
- Keep `DIGITALOCEAN_ACCESS_TOKEN`, `PLATFORM_ENV_FILE`, `PLATFORM_SSH_HOST`, `PLATFORM_SSH_PORT`, `PLATFORM_SSH_PRIVATE_KEY`, `PLATFORM_SSH_USER`, and `PLATFORM_FIREWALL_ID` for the new deploy workflow.

## Final Verification

Run:

```bash
gh run list --repo raniendu/platform --limit 5
doctl compute droplet list
doctl apps list
doctl databases list
doctl compute volume list
doctl compute load-balancer list
curl -sS -o /dev/null -w '%{http_code}\n' https://raniendu.dev/
curl -sS -o /dev/null -w '%{http_code}\n' https://www.raniendu.dev/
curl -sS -o /dev/null -w '%{http_code}\n' https://prefect.raniendu.dev/api/health
curl -sS -o /dev/null -w '%{http_code}\n' https://flow.raniendu.dev/
```

Expected result: only the consolidated platform resources remain for these services, and the public route statuses are `200`, `301`, `401`, `200`.
