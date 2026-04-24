# Development Guide

This guide covers everything you need to know for developing DAGs and contributing to this Airflow project.

## Table of Contents

- [Quick Start](#quick-start)
- [Development Environment](#development-environment)
- [Project Architecture](#project-architecture)
- [Working with DAGs](#working-with-dags)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Debugging](#debugging)
- [Common Development Tasks](#common-development-tasks)
- [Best Practices](#best-practices)

---

## Quick Start

### Tool Installation (macOS)

```bash
# Install Docker Desktop
brew install --cask docker

# Install UV (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Launch Docker Desktop
open -a Docker
```

### Get Running

```bash
uv sync                                          # Install dependencies
docker compose -f docker-compose.local.yml up    # Start Airflow
# Open http://localhost:8080 (login with any username)
```

---

## Development Environment

### Local Stack Overview

| Component | Local Dev | Production |
|-----------|-----------|------------|
| Executor | SequentialExecutor | LocalExecutor |
| Database | SQLite | PostgreSQL |
| Authentication | Disabled (all admins) | Password-based |
| SSL | None | Let's Encrypt |

### Starting the Environment

```bash
docker compose -f docker-compose.local.yml up      # Foreground
docker compose -f docker-compose.local.yml up -d   # Background
docker compose -f docker-compose.local.yml logs -f # View logs
```

### Stopping the Environment

```bash
docker compose -f docker-compose.local.yml stop    # Stop (keep data)
docker compose -f docker-compose.local.yml down    # Stop and remove
docker compose -f docker-compose.local.yml down -v # Full reset
```

### Rebuilding After Changes

```bash
docker compose -f docker-compose.local.yml build      # Rebuild only
docker compose -f docker-compose.local.yml up --build # Rebuild and start
```

---

## Project Architecture

### Directory Structure

```
.
├── dags/                    # DAG definitions (mounted into containers)
│   ├── __init__.py
│   ├── example_dag.py       # Example DAG template
│   └── utils/               # Shared utilities for DAGs
├── plugins/                 # Custom Airflow plugins
├── logs/                    # Airflow logs (auto-generated)
├── scripts/                 # Utility scripts
│   ├── validate-dags.py     # DAG syntax validation
│   ├── generate-fernet-key.py
│   └── create-admin.py
├── tests/                   # Test files
├── docker-compose.local.yml # Local development stack
├── docker-compose.yml       # Production stack
├── Dockerfile               # Custom Airflow image
└── pyproject.toml           # Python dependencies
```

### Services Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Local Development                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │  Webserver   │    │  Scheduler   │                   │
│  │  (port 8080) │    │              │                   │
│  └──────┬───────┘    └──────┬───────┘                   │
│         │                   │                            │
│         └─────────┬─────────┘                            │
│                   │                                      │
│           ┌───────▼───────┐                              │
│           │    SQLite     │                              │
│           │   Database    │                              │
│           └───────────────┘                              │
│                                                          │
│  Mounted Volumes:                                        │
│  • ./dags → /opt/airflow/dags                           │
│  • ./logs → /opt/airflow/logs                           │
│  • ./plugins → /opt/airflow/plugins                     │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Working with DAGs

### Creating a New DAG

1. Create a new Python file in the `dags/` directory:

```python
"""
My Custom DAG

Description of what this DAG does.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator


def my_task_function(**context):
    """Task logic goes here."""
    print("Executing my task")
    return "Success"


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="my_custom_dag",
    default_args=default_args,
    description="Description of my DAG",
    schedule="@daily",  # or cron: "0 0 * * *"
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["custom", "example"],
) as dag:
    
    start = EmptyOperator(task_id="start")
    
    process = PythonOperator(
        task_id="process_data",
        python_callable=my_task_function,
    )
    
    end = EmptyOperator(task_id="end")
    
    start >> process >> end
```

2. Validate the DAG:

```bash
python scripts/validate-dags.py
```

3. The DAG will be automatically detected by Airflow (may take up to 30 seconds).

### DAG File Naming Conventions

- Use lowercase with underscores: `my_data_pipeline.py`
- Prefix with domain/team: `analytics_daily_report.py`
- Keep names descriptive but concise

### Common Operators

```python
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.sensors.filesystem import FileSensor
from airflow.providers.http.operators.http import SimpleHttpOperator
```

### Task Dependencies

```python
# Linear
task1 >> task2 >> task3

# Fan-out
task1 >> [task2, task3, task4]

# Fan-in
[task1, task2, task3] >> task4

# Complex
task1 >> task2
task1 >> task3
[task2, task3] >> task4
```

### Using XComs for Data Passing

```python
def push_data(**context):
    return {"key": "value", "count": 42}

def pull_data(**context):
    ti = context['ti']
    data = ti.xcom_pull(task_ids='push_task')
    print(f"Received: {data}")

push_task = PythonOperator(
    task_id='push_task',
    python_callable=push_data,
)

pull_task = PythonOperator(
    task_id='pull_task',
    python_callable=pull_data,
)
```

---

## Testing

### Running Tests

```bash
# Install dev dependencies
uv sync

# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_dags.py

# Run with coverage
uv run pytest --cov=dags
```

### DAG Validation

Always validate DAGs before committing:

```bash
python scripts/validate-dags.py
```

This script:
- Imports all DAG files to check for syntax errors
- Validates Python imports
- Returns exit code 0 on success, 1 on failure
- Runs automatically in CI/CD pipeline

### Writing DAG Tests

```python
# tests/test_dags.py
import pytest
from airflow.models import DagBag


def test_dag_loaded():
    """Test that DAGs load without errors."""
    dag_bag = DagBag(dag_folder='dags', include_examples=False)
    assert len(dag_bag.import_errors) == 0, f"DAG import errors: {dag_bag.import_errors}"


def test_dag_has_tasks():
    """Test that example_dag has expected tasks."""
    dag_bag = DagBag(dag_folder='dags', include_examples=False)
    dag = dag_bag.get_dag('example_dag')
    assert dag is not None
    assert len(dag.tasks) > 0
```

---

## Code Quality

### Linting and Formatting

```bash
# Format code with black (if installed)
black dags/

# Sort imports with isort (if installed)
isort dags/

# Type checking with mypy (if installed)
mypy dags/
```

### Pre-commit Checks

Before committing, always:

1. Validate DAGs: `python scripts/validate-dags.py`
2. Run tests: `uv run pytest`
3. Check formatting

---

## Debugging

### Viewing Logs

```bash
# All logs
docker compose -f docker-compose.local.yml logs -f

# Webserver only
docker compose -f docker-compose.local.yml logs -f airflow-webserver

# Scheduler only
docker compose -f docker-compose.local.yml logs -f airflow-scheduler

# Last 100 lines
docker compose -f docker-compose.local.yml logs --tail=100
```

### Accessing the Container Shell

```bash
# Webserver container
docker exec -it airflow_webserver_local bash

# Scheduler container
docker exec -it airflow_scheduler_local bash

# Run Airflow CLI commands
docker exec -it airflow_webserver_local airflow dags list
docker exec -it airflow_webserver_local airflow tasks list example_dag
```

### Common Issues

#### DAGs Not Appearing

1. Check for syntax errors:
   ```bash
   python scripts/validate-dags.py
   ```

2. Check scheduler logs:
   ```bash
   docker compose -f docker-compose.local.yml logs airflow-scheduler
   ```

3. Verify file is in `dags/` directory

4. Wait 30 seconds for scheduler to detect changes

#### Import Errors

1. Check if dependencies are in `pyproject.toml`
2. Rebuild the container:
   ```bash
   docker compose -f docker-compose.local.yml build
   docker compose -f docker-compose.local.yml up
   ```

#### Port 8080 Already in Use

```bash
# Find process using port
lsof -i :8080

# Or change port in docker-compose.local.yml
ports:
  - "8081:8080"
```

#### Database Issues

```bash
# Reset database completely
docker compose -f docker-compose.local.yml down -v
docker compose -f docker-compose.local.yml up
```

---

## Common Development Tasks

### Adding Python Dependencies

1. Edit `pyproject.toml`:
   ```toml
   dependencies = [
       "apache-airflow>=3.1.7",
       "pandas>=2.0.0",  # Add new dependency
   ]
   ```

2. Update lock file:
   ```bash
   uv lock
   ```

3. Rebuild containers:
   ```bash
   docker compose -f docker-compose.local.yml build
   docker compose -f docker-compose.local.yml up
   ```

### Creating Utility Functions

Place shared code in `dags/utils/`:

```python
# dags/utils/helpers.py
def format_date(dt):
    return dt.strftime("%Y-%m-%d")

def send_notification(message):
    # notification logic
    pass
```

Use in DAGs:

```python
from utils.helpers import format_date, send_notification
```

### Working with Variables and Connections

In the Airflow UI (http://localhost:8080):

- **Variables**: Admin → Variables
- **Connections**: Admin → Connections

Or via CLI:

```bash
# Set variable
docker exec -it airflow_webserver_local airflow variables set my_var "my_value"

# Get variable
docker exec -it airflow_webserver_local airflow variables get my_var
```

---

## Best Practices

### DAG Design

1. **Keep DAGs simple** - One DAG per workflow
2. **Use meaningful task IDs** - `extract_sales_data` not `task1`
3. **Set appropriate retries** - Usually 1-3 retries
4. **Use tags** - For filtering in the UI
5. **Document your DAGs** - Docstrings at the top

### Performance

1. **Avoid heavy imports at module level** - Import inside functions when possible
2. **Use pools** - To limit concurrent tasks
3. **Set appropriate timeouts** - Prevent hung tasks

### Security

1. **Never hardcode credentials** - Use Airflow Variables or Connections
2. **Use Fernet encryption** - For sensitive data
3. **Limit DAG access** - Use RBAC in production

### Version Control

1. **Validate before committing** - `python scripts/validate-dags.py`
2. **Test locally first** - Before pushing to main
3. **Use meaningful commit messages** - Describe DAG changes

---

## Quick Reference

### Useful Commands

```bash
# Start local environment
docker compose -f docker-compose.local.yml up -d

# Stop local environment
docker compose -f docker-compose.local.yml down

# View logs
docker compose -f docker-compose.local.yml logs -f

# Validate DAGs
python scripts/validate-dags.py

# Run tests
uv run pytest

# Rebuild after changes
docker compose -f docker-compose.local.yml up --build

# Access container shell
docker exec -it airflow_webserver_local bash

# List DAGs
docker exec -it airflow_webserver_local airflow dags list
```

### Useful URLs (Local)

- Airflow UI: http://localhost:8080
- Health Check: http://localhost:8080/health

---

## Getting Help

- [Apache Airflow Documentation](https://airflow.apache.org/docs/)
- [Airflow GitHub](https://github.com/apache/airflow)
- Check `logs/` directory for detailed error messages
- Review scheduler logs for DAG parsing issues
