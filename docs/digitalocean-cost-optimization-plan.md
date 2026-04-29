# DigitalOcean Cost Optimization Plan

Pricing snapshot: 2026-04-26. Prices are public USD list prices before tax, support, unusual bandwidth, and one-off snapshot storage.

## Current State As Of 2026-04-27

The monorepo migration is live and the old DigitalOcean resources have been removed.

GitHub:

- Repository: `raniendu/platform`
- Default branch: `main`
- Latest successful production deploy before this note: GitHub Actions run `24959751917`
- Latest deployment commit at that time: `55d4a07d9610ce8820b49654480e756212af00a6`
- Deploy path: `.github/workflows/deploy.yml`
- Deploy mechanism: manual `workflow_dispatch`, Terraform adopt/plan/apply for the shared Droplet and firewall, SSH to the Droplet, upload repo and `PLATFORM_ENV_FILE`, run Docker Compose, force-recreate Caddy, then run public smoke checks.
- Important deploy behavior: the smoke checks intentionally retry because Caddy and Airflow can take a few seconds to become reachable after container recreation.

DigitalOcean:

| Resource | Current state |
| --- | --- |
| Droplet `platform-shared` | active, ID `567106036`, IP `174.138.59.96`, 2 vCPU, 4 GiB RAM, 80 GiB disk, backups enabled |
| Firewall `platform-shared-firewall` | active, ID `f08d6940-f470-47ce-8dba-ffad3ef16832`, attached to `platform-shared` |
| Old Droplet `prefect-server` | destroyed on 2026-04-27 without snapshot |
| Old App Platform app `dot-dev-app` | deleted on 2026-04-27 |
| Old firewall `prefect-server-firewall` | deleted on 2026-04-27 |
| Managed databases | none observed |
| Volumes | none observed |
| Load balancers | none observed |
| Standalone snapshots | none observed |

Current public smoke-check expectations:

```text
https://raniendu.dev/ -> 200
https://www.raniendu.dev/ -> 301
https://prefect.raniendu.dev/api/health -> 401
https://flow.raniendu.dev/ -> 200
```

`401` for Prefect is expected because Caddy basic auth protects the route before the Prefect health endpoint is reached.

Current DNS:

```text
A      @        174.138.59.96
CNAME  www      raniendu.dev
A      prefect  174.138.59.96
A      flow     174.138.59.96
```

Do not reintroduce old App Platform custom domains or the old Prefect Droplet.

## Goal

Reduce the consolidated platform cost while keeping the monorepo, one public runtime, GitHub Actions deploys, Caddy-managed HTTPS, Prefect, and Airflow.

Current consolidated cost:

| Droplet size | Base cost | Weekly backups | Total |
| --- | ---: | ---: | ---: |
| `s-2vcpu-4gb` | $24.00 | $4.80 | $28.80 |

Pre-migration old infrastructure baseline from `docs/digitalocean-cost-comparison.md`:

| Baseline | Estimated monthly cost |
| --- | ---: |
| Visible old Prefect Droplet plus DotDev App Platform app | $11.00 |
| Historical old infra if Airflow 1 GiB Droplet were enabled | $17.00 |

Those old resources are now gone. Use those numbers only as historical cost baselines, not as active overlap.

## Target

Migration target: `s-1vcpu-2gb`. The existing `s-2vcpu-4gb` Droplet cannot be resized there in place because its disk is already larger than the target plan's disk.

| Droplet size | Base cost | Weekly backups | Total | Assessment |
| --- | ---: | ---: | ---: | --- |
| `s-1vcpu-2gb` | $12.00 | $2.40 | $14.40 | Best first target. Cheaper than old infra when Airflow is included. |
| `s-1vcpu-1gb` | $6.00 | $1.20 | $7.20 | Beats the visible old $11 baseline, but high risk unless runtime memory is reduced first. |
| `s-2vcpu-2gb` | $18.00 | $3.60 | $21.60 | Safer CPU headroom, but still above the old Airflow-included baseline. |

Recommendation: optimize first, consolidate Postgres, then migrate to a new `s-1vcpu-2gb` Droplet. Observe for at least one week before deciding whether a controlled `s-1vcpu-1gb` experiment is worth the operational risk.

## Why Not Resize Immediately To 1 GiB

The platform currently runs:

- Caddy
- DotDev
- Prefect server
- Prefect worker
- Prefect Postgres
- Airflow webserver/API server
- Airflow scheduler
- Airflow Postgres

It also builds Docker images on the Droplet during deploy. Airflow plus Prefect plus two Postgres containers can fit in 2 GiB with conservative settings, but 1 GiB leaves little room for deploy-time builds, database spikes, Airflow DAG parsing, and package/import overhead.

## Optimization Sequence

## Implementation Context For A Fresh Codex Session

Start in:

```bash
cd /Users/raniendu/PycharmProjects/platform
```

Read these first:

- `AGENTS.md`
- `README.md`
- `docs/developer-guide.md`
- `docs/deployment.md`
- `docs/operations.md`
- `docs/digitalocean-cost-comparison.md`
- this file

Key files likely to change:

- `.github/workflows/deploy.yml`
- `.github/workflows/ci.yml`
- `deploy/compose/docker-compose.prod.yml`
- `deploy/compose/docker-compose.local.yml`
- `infra/terraform/variables.tf`
- `infra/terraform/terraform.tfvars.example`
- app Dockerfiles under `apps/dotdev/`, `apps/prefect/`, and `apps/flow/`

Secrets and private state:

- Do not print or commit `.env.production.generated`, `.env.production.credentials`, `.env.local`, Terraform state, SSH keys, or GitHub secret values.
- GitHub production secrets already exist for the current deploy path.
- `PLATFORM_ENV_FILE` is the GitHub secret that becomes `/opt/platform/.env.production`.

Current deploy assumptions:

- Production Compose uses SHA-pinned GHCR image references supplied by the deploy workflow; local Compose remains build-based for development.
- Local Compose should remain build-based for development.
- Caddy has named volumes for certificates.
- Airflow and Prefect each currently have their own Postgres container and volume.

Before implementing any cost change:

```bash
git status --short --branch
gh run list --repo raniendu/platform --limit 5
doctl compute droplet get 567106036
doctl compute firewall get f08d6940-f470-47ce-8dba-ffad3ef16832
curl -sS -o /dev/null -w 'raniendu.dev %{http_code}\n' https://raniendu.dev/
curl -sS -o /dev/null -w 'www.raniendu.dev %{http_code}\n' https://www.raniendu.dev/
curl -sS -o /dev/null -w 'prefect.raniendu.dev/api/health %{http_code}\n' https://prefect.raniendu.dev/api/health
curl -sS -o /dev/null -w 'flow.raniendu.dev %{http_code}\n' https://flow.raniendu.dev/
```

Expected route statuses: `200`, `301`, `401`, `200`.

### Phase 1: Measure Current Runtime

Goal: distinguish steady-state memory from deploy/build memory.

Preferred way to gather host metrics is through the existing deploy SSH credentials in GitHub Actions. If running locally, SSH access may not be available unless the correct key is loaded and the firewall allows your current IP.

Commands on the Droplet:

```bash
cd /opt/platform
docker stats --no-stream
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production ps
free -h
df -h
docker system df
```

Record:

- idle memory by container,
- memory during a GitHub deploy,
- disk usage under `/opt/platform`,
- whether Airflow scheduler and Prefect worker remain healthy after deploy.

Useful measurement implementation:

- Add a temporary or manually dispatched GitHub Actions diagnostics workflow that SSHes to the Droplet and runs the commands above.
- Do not print `.env.production`.
- Keep the diagnostics workflow read-only.
- Remove or keep it manual-only after collecting the baseline.

Do not resize until this baseline is captured.

### Phase 2: Move Image Builds Off The Droplet

Goal: make the Droplet pull images instead of building them.

Status in this repo: implemented in the production deploy path. GitHub Actions builds DotDev, Prefect, and Airflow images, pushes SHA-tagged images to GHCR, appends those image refs to `.env.production` during deploy, and runs production Compose with `up -d --no-build`.

Approach:

1. Add a GitHub Actions build job that builds DotDev, Prefect, and Airflow images.
2. Push images to GitHub Container Registry.
3. Replace production Compose `build:` entries with image references.
4. Keep local Compose build-based.
5. Update deploy to pull images and run `docker compose up -d` without building.

Suggested image names:

```text
ghcr.io/raniendu/platform/dotdev:<git-sha>
ghcr.io/raniendu/platform/prefect:<git-sha>
ghcr.io/raniendu/platform/airflow:<git-sha>
```

Suggested production env variables:

```text
DOTDEV_IMAGE=ghcr.io/raniendu/platform/dotdev:<git-sha>
PREFECT_IMAGE=ghcr.io/raniendu/platform/prefect:<git-sha>
AIRFLOW_IMAGE=ghcr.io/raniendu/platform/airflow:<git-sha>
```

Production Compose can then use:

```yaml
image: ${DOTDEV_IMAGE}
```

for DotDev and equivalent variables for Prefect and Airflow services. Use the same Prefect image for `prefect-server` and `prefect-worker`; use the same Airflow image for `airflow-init`, `airflow-webserver`, and `airflow-scheduler`.

Expected benefit:

- lower deploy-time CPU and memory pressure,
- faster deploys,
- safer 2 GiB Droplet target,
- cleaner rollback by image tag.

Verification:

```bash
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production.generated config
gh run list --repo raniendu/platform --limit 5
curl -sS -o /dev/null -w '%{http_code}\n' https://raniendu.dev/
curl -sS -o /dev/null -w '%{http_code}\n' https://prefect.raniendu.dev/api/health
curl -sS -o /dev/null -w '%{http_code}\n' https://flow.raniendu.dev/
```

Expected public statuses: `200`, `401`, `200`.

Do not resize in the same commit as this change. First prove a normal deploy works with remote-built images on the current 4 GiB Droplet.

### Phase 3: Consolidate Postgres Containers

Goal: save memory without moving to a managed database.

Status in this repo: implemented in the production deploy path. Production Compose now defines one `platform-postgres` container with separate `prefect` and `airflow` roles/databases. The deploy workflow runs a one-time dump/restore migration before starting the new app containers and stops legacy Postgres containers only after public smoke checks pass.

Approach:

1. Run one Postgres container.
2. Create separate `prefect` and `airflow` databases.
3. Create separate database users/passwords.
4. Keep separate logical volumes only if a migration path needs temporary side-by-side data; otherwise move to one Postgres data volume after backup.

Expected benefit:

- lower memory footprint,
- fewer containers,
- simpler backups.

Risk:

- this is a data migration and needs a maintenance window.
- rollback requires preserving the old Prefect and Airflow Postgres volumes until the new shared Postgres is verified.

Verification:

```bash
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production ps
curl -sS -o /dev/null -w '%{http_code}\n' https://prefect.raniendu.dev/api/health
curl -sS -o /dev/null -w '%{http_code}\n' https://flow.raniendu.dev/
```

Expected public statuses: `401`, `200`.

Do not combine this phase with Droplet resizing. This phase touches data volumes and should have its own backup, deploy, verification, and rollback window.

### Phase 4: Tune Airflow For Personal-Scale Runtime

Goal: avoid paying for unused scheduler and worker headroom.

Status in this repo: implemented for production Compose with the conservative settings below.

Candidate settings:

```text
AIRFLOW__CORE__PARALLELISM=2
AIRFLOW__CORE__MAX_ACTIVE_TASKS_PER_DAG=2
AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG=1
AIRFLOW__SCHEDULER__PARSING_PROCESSES=1
AIRFLOW__SCHEDULER__MIN_FILE_PROCESS_INTERVAL=60
AIRFLOW__SCHEDULER__DAG_DIR_LIST_INTERVAL=120
```

These can be added to the shared Airflow environment block in `deploy/compose/docker-compose.prod.yml` and mirrored locally only if local behavior should match production.

Expected benefit:

- lower scheduler CPU spikes,
- lower memory pressure from DAG parsing.

Risk:

- DAGs run with less parallelism.
- schedule latency can increase slightly, which is acceptable for personal-scale workflows.

### Phase 5: Migrate To A New `s-1vcpu-2gb` Droplet

Goal: reduce steady-state cost to about $14.40/month with weekly backups.

Status: not safe as an in-place resize for the current Droplet. The existing `platform-shared` Droplet has an 80 GiB disk. DigitalOcean rejected both `resize_disk = false` and `resize_disk = true` attempts to move it to `s-1vcpu-2gb` because that target size has a smaller 50 GiB disk. Reaching `s-1vcpu-2gb` requires a new smaller-disk Droplet and a controlled migration.

Preconditions:

- Phase 1 baseline captured.
- Phase 2 build-off-host completed or deploy-time memory shown to be safe.
- Latest GitHub CI passed.
- Latest GitHub deploy passed.
- Public smoke checks pass.
- Postgres consolidation has deployed successfully and has been accepted.
- A fresh Droplet backup or snapshot exists.

Plan:

1. Confirm the target size and disk difference:

   ```bash
   doctl compute size list | rg 's-1vcpu-2gb|s-2vcpu-4gb'
   ```

2. Open a separate migration PR/workflow for the new Droplet, following `docs/smaller-droplet-migration.md`. Do not make the normal `deploy.yml` create a second Droplet.
3. Create a new `s-1vcpu-2gb` Droplet from GitHub Actions behind a typed manual confirmation.
4. Deploy the current stack to the new Droplet and restore consolidated Postgres dumps.
5. Verify service health on the new host before DNS cutover.
6. Update Squarespace DNS to the new Droplet IP.
7. Run public smoke checks.
8. Decommission the old `s-2vcpu-4gb` Droplet only after explicit approval.

Terraform follow-up:

- Terraform now sets `resize_disk = false` on the Droplet so the size change uses CPU/RAM-only resize semantics.
- `infra/terraform/variables.tf`, `infra/terraform/terraform.tfvars.example`, and `.env.example` keep routine deploys on `s-2vcpu-4gb` so Postgres consolidation can deploy before the new-Droplet migration.
- The deploy workflow imports an existing `platform-shared` Droplet before applying, fails if DigitalOcean inventory cannot be read, refuses duplicate matching Droplets, refuses Droplet delete/replace plans, and refuses creating a new Droplet when one already exists.
- Production Terraform apply runs behind the GitHub `production` environment approval.
- Because the existing disk cannot shrink in place, the normal deploy workflow remains intentionally single-Droplet-safe; a new-Droplet migration must be separate from routine deploys.

Verification:

```bash
doctl compute droplet get 567106036
docker stats --no-stream
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production ps
curl -sS -o /dev/null -w '%{http_code}\n' https://raniendu.dev/
curl -sS -o /dev/null -w '%{http_code}\n' https://www.raniendu.dev/
curl -sS -o /dev/null -w '%{http_code}\n' https://prefect.raniendu.dev/api/health
curl -sS -o /dev/null -w '%{http_code}\n' https://flow.raniendu.dev/
```

Expected public statuses: `200`, `301`, `401`, `200`.

Rollback:

- before DNS cutover, keep using the old `s-2vcpu-4gb` Droplet,
- after DNS cutover, point Squarespace DNS back to the old Droplet IP if it has not been decommissioned,
- rerun the deploy workflow on the chosen host,
- verify the same smoke checks.

### Phase 6: Optional `s-1vcpu-1gb` Experiment

Goal: test whether the consolidated platform can beat the visible old $11/month baseline.

Only attempt this after:

- off-host image builds are in production,
- Postgres is consolidated or measured memory proves two Postgres containers are fine,
- Airflow has personal-scale settings,
- one week on `s-1vcpu-2gb` shows healthy memory headroom.

Expected cost: about $7.20/month with weekly backups.

Stop criteria:

- swap pressure,
- OOM kills,
- Airflow scheduler instability,
- Prefect worker missed runs,
- deploy failures caused by host pressure.

Rollback immediately to `s-1vcpu-2gb` or `s-2vcpu-4gb` if any stop criterion appears.

## Other Cost Levers

Backups:

- Disabling weekly backups saves 20% of Droplet cost.
- On `s-1vcpu-2gb`, that saves $2.40/month.
- Keep backups enabled until old infrastructure is decommissioned and the new platform has run stably.

Old resource deprecation:

- Completed on 2026-04-27: `prefect-server`, `dot-dev-app`, and `prefect-server-firewall` were removed.
- There is no longer old-resource overlap for this stack in DigitalOcean inventory.

Airflow alternatives:

- Replacing Airflow with scheduled Prefect flows, cron, or serverless jobs could reduce runtime needs further.
- That is a product/runtime change, not just an infrastructure optimization.

## Decision Gates

| Gate | Decision |
| --- | --- |
| After Phase 1 | Is runtime memory low enough to resize safely? |
| After Phase 2 | Can deployments run without building on the Droplet? |
| After Phase 5 | Is `s-1vcpu-2gb` stable for a week? |
| After Phase 6 | Is the risk of `s-1vcpu-1gb` acceptable compared with the extra $7.20/month saved? |

## Recommendation

Implement Phase 1 and Phase 2 first, consolidate Postgres, then migrate to a new `s-1vcpu-2gb` Droplet. This should cut consolidated monthly cost from $28.80 to $14.40 while preserving the monolithic architecture. Treat `s-1vcpu-1gb` as a later experiment, not the default target.
