# DigitalOcean Cost Optimization Plan

Pricing snapshot: 2026-04-26. Prices are public USD list prices before tax, support, unusual bandwidth, and one-off snapshot storage.

## Goal

Reduce the consolidated platform cost while keeping the monorepo, one public runtime, GitHub Actions deploys, Caddy-managed HTTPS, Prefect, and Airflow.

Current consolidated cost:

| Droplet size | Base cost | Weekly backups | Total |
| --- | ---: | ---: | ---: |
| `s-2vcpu-4gb` | $24.00 | $4.80 | $28.80 |

Old infrastructure baseline from `docs/digitalocean-cost-comparison.md`:

| Baseline | Estimated monthly cost |
| --- | ---: |
| Visible old Prefect Droplet plus DotDev App Platform app | $11.00 |
| Historical old infra if Airflow 1 GiB Droplet were enabled | $17.00 |

## Target

Primary target: `s-1vcpu-2gb`.

| Droplet size | Base cost | Weekly backups | Total | Assessment |
| --- | ---: | ---: | ---: | --- |
| `s-1vcpu-2gb` | $12.00 | $2.40 | $14.40 | Best first target. Cheaper than old infra when Airflow is included. |
| `s-1vcpu-1gb` | $6.00 | $1.20 | $7.20 | Beats the visible old $11 baseline, but high risk unless runtime memory is reduced first. |
| `s-2vcpu-2gb` | $18.00 | $3.60 | $21.60 | Safer CPU headroom, but still above the old Airflow-included baseline. |

Recommendation: optimize first, resize to `s-1vcpu-2gb`, observe for at least one week, then decide whether a controlled `s-1vcpu-1gb` experiment is worth the operational risk.

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

### Phase 1: Measure Current Runtime

Goal: distinguish steady-state memory from deploy/build memory.

Commands:

```bash
docker stats --no-stream
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production ps
free -h
df -h
```

Record:

- idle memory by container,
- memory during a GitHub deploy,
- disk usage under `/opt/platform`,
- whether Airflow scheduler and Prefect worker remain healthy after deploy.

Do not resize until this baseline is captured.

### Phase 2: Move Image Builds Off The Droplet

Goal: make the Droplet pull images instead of building them.

Approach:

1. Add a GitHub Actions build job that builds DotDev, Prefect, and Airflow images.
2. Push images to GitHub Container Registry.
3. Replace production Compose `build:` entries with pinned image references.
4. Keep local Compose build-based.
5. Update deploy to pull images and run `docker compose up -d` without building.

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

### Phase 3: Consolidate Postgres Containers

Goal: save memory without moving to a managed database.

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

### Phase 4: Tune Airflow For Personal-Scale Runtime

Goal: avoid paying for unused scheduler and worker headroom.

Candidate settings:

```text
AIRFLOW__CORE__PARALLELISM=2
AIRFLOW__CORE__MAX_ACTIVE_TASKS_PER_DAG=2
AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG=1
AIRFLOW__SCHEDULER__PARSING_PROCESSES=1
AIRFLOW__SCHEDULER__MIN_FILE_PROCESS_INTERVAL=60
AIRFLOW__SCHEDULER__DAG_DIR_LIST_INTERVAL=120
```

Expected benefit:

- lower scheduler CPU spikes,
- lower memory pressure from DAG parsing.

Risk:

- DAGs run with less parallelism.
- schedule latency can increase slightly, which is acceptable for personal-scale workflows.

### Phase 5: Resize To `s-1vcpu-2gb`

Goal: reduce steady-state cost to about $14.40/month with weekly backups.

Preconditions:

- Phase 1 baseline captured.
- Phase 2 build-off-host completed or deploy-time memory shown to be safe.
- Latest GitHub CI passed.
- Latest GitHub deploy passed.
- Public smoke checks pass.
- A fresh Droplet backup or snapshot exists.

Plan:

1. Confirm the target size is available:

   ```bash
   doctl compute size list | rg 's-1vcpu-2gb|s-2vcpu-4gb'
   ```

2. Resize with CPU/RAM-only semantics when possible. Do not intentionally grow disk unless needed.
3. Reboot if required by the resize operation.
4. Run a production deploy.
5. Watch container health and public endpoints.

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

- resize back to `s-2vcpu-4gb`,
- rerun the deploy workflow,
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

- Destroying `prefect-server` and `dot-dev-app` saves about $11/month.
- Follow `docs/deprecation-plan.md`; do not delete resources without explicit approval.

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

Implement Phase 1 and Phase 2 first, then resize to `s-1vcpu-2gb`. This should cut consolidated monthly cost from $28.80 to $14.40 while preserving the monolithic architecture. Treat `s-1vcpu-1gb` as a later experiment, not the default target.
