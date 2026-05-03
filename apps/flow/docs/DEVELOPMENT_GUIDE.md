# Airflow Development Guide

This guide covers Airflow DAG development inside the `platform` monorepo.

## Current Deployment Assumptions

- Airflow is one app in the shared platform stack.
- Production is not a standalone Airflow Droplet, Terraform stack, or Nginx deployment.
- Local development uses `deploy/compose/docker-compose.local.yml`.
- Production uses `deploy/compose/docker-compose.prod.yml` and Caddy.
- Production deploys are manual GitHub Actions runs from `.github/workflows/deploy.yml`.

Run commands from the repository root unless a command says otherwise.

## Local Setup

```bash
cp .env.example .env.local
uv sync --project apps/flow
```

Start the local platform:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build
```

Local Airflow URLs:

- UI through Caddy: `http://flow.localhost`
- direct UI: `http://localhost:8080`
- health: `http://localhost:8080/health`

Local Airflow uses the simple auth manager in all-admins mode. Enter any username.

Follow logs:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local logs -f airflow-webserver
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local logs -f airflow-scheduler
```

Stop local services:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local down
```

Reset local Airflow state:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local down -v
```

## Creating DAGs

Create DAG files under `apps/flow/dags/`.

```python
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator


def process_data() -> str:
    return "ok"


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


with DAG(
    dag_id="example_pipeline",
    default_args=default_args,
    description="Example Airflow DAG",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["example"],
) as dag:
    start = EmptyOperator(task_id="start")
    process = PythonOperator(task_id="process_data", python_callable=process_data)
    end = EmptyOperator(task_id="end")

    start >> process >> end
```

Keep module imports cheap. Airflow parses DAG files frequently, and production runs on a 2 GiB Droplet with conservative scheduler settings.

## Validation And Tests

Validate DAG imports:

```bash
uv run --project apps/flow python apps/flow/scripts/validate-dags.py
```

Run Airflow tests:

```bash
uv run --project apps/flow pytest apps/flow/tests/
```

Run a specific test:

```bash
uv run --project apps/flow pytest apps/flow/tests/test_dags.py -q
```

Validation checks that DAG files import cleanly and returns a non-zero exit code on import failures.

## Debugging

List local containers:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local ps
```

Open a shell:

```bash
docker exec -it platform-airflow-webserver-local bash
```

Run Airflow CLI commands:

```bash
docker exec -it platform-airflow-webserver-local airflow dags list
docker exec -it platform-airflow-webserver-local airflow tasks list example_pipeline
```

If DAGs are not visible:

1. Run the DAG validator.
2. Check `airflow-scheduler` logs.
3. Confirm the file is under `apps/flow/dags/`.
4. Wait for the scheduler parse interval.

## Dependencies

Airflow is pinned in `apps/flow/Dockerfile` and `apps/flow/pyproject.toml`.

### Adding Python Dependencies

1. Edit `pyproject.toml`:
   ```toml
   dependencies = [
       "apache-airflow==3.1.7",
       "pandas>=2.0.0",  # Add new dependency
   ]
   ```

2. Update lock file:
   ```bash
   uv lock --project apps/flow
   ```

3. Rebuild containers:
   ```bash
   docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local build airflow-init airflow-webserver airflow-scheduler
   ```

Then rerun validation and tests.

## Production Deployment

Do not deploy Airflow separately. Production deployment is the shared manual workflow:

```bash
gh workflow run deploy.yml --repo raniendu/platform --ref main
gh run watch --repo raniendu/platform --exit-status
```

Expected public smoke result for Airflow:

```text
flow.raniendu.dev -> 200
```

## Production Data

Local development uses a dedicated `airflow-postgres` container and local Docker volume.

Production uses the shared `platform-postgres` container with:

- database: `airflow`;
- role: `airflow`;
- password from `AIRFLOW_POSTGRES_PASSWORD` inside `PLATFORM_ENV_FILE`.

Airflow logs, plugins, and auth config are stored in Docker volumes managed by the production Compose stack.

## Production Resource Constraints

Production uses personal-scale Airflow settings:

```text
AIRFLOW__CORE__PARALLELISM=2
AIRFLOW__CORE__MAX_ACTIVE_TASKS_PER_DAG=2
AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG=1
AIRFLOW__SCHEDULER__PARSING_PROCESSES=1
AIRFLOW__SCHEDULER__MIN_FILE_PROCESS_INTERVAL=60
AIRFLOW__SCHEDULER__DAG_DIR_LIST_INTERVAL=120
```

Design DAGs so they do not require high task parallelism or heavy import-time work.

## Useful Commands

```bash
uv sync --project apps/flow
uv run --project apps/flow python apps/flow/scripts/validate-dags.py
uv run --project apps/flow pytest apps/flow/tests/
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local logs -f airflow-webserver
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local logs -f airflow-scheduler
```
