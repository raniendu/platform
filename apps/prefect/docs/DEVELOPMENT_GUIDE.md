# Development Guide

This guide covers how to develop, test, and manage Prefect flows in this project.

---

## Table of Contents

1. [Local Development Setup](#1-local-development-setup)
2. [Creating New Flows](#2-creating-new-flows)
3. [Testing Flows](#3-testing-flows)
4. [Deploying Flows](#4-deploying-flows)
5. [Removing Flows](#5-removing-flows)
6. [Best Practices](#6-best-practices)

---

## 1. Local Development Setup

### Start Local Environment

```bash
# Install dependencies
uv sync

# Start Prefect server, PostgreSQL, and worker
./scripts/local-up.sh

# Access Prefect UI at http://localhost:4200
```

### Stop Local Environment

```bash
./scripts/local-down.sh
```

### View Logs

```bash
docker compose -f docker-compose.local.yml logs -f

# Specific service
docker compose -f docker-compose.local.yml logs -f prefect-server
```

---

## 2. Creating New Flows

### Basic Flow Structure

Create a new file in `flows/` directory:

```python
# flows/my_flow.py
from prefect import flow, task, get_run_logger


@task
def extract_data(source: str) -> list:
    """Extract data from source."""
    logger = get_run_logger()
    logger.info(f"Extracting from {source}")
    return ["item1", "item2", "item3"]


@task
def transform_data(data: list) -> list:
    """Transform the data."""
    logger = get_run_logger()
    logger.info(f"Transforming {len(data)} items")
    return [item.upper() for item in data]


@task
def load_data(data: list, destination: str) -> int:
    """Load data to destination."""
    logger = get_run_logger()
    logger.info(f"Loading {len(data)} items to {destination}")
    return len(data)


@flow(name="my-etl-flow", log_prints=True)
def my_etl_flow(source: str = "default", destination: str = "output") -> dict:
    """
    Example ETL flow.
    
    Args:
        source: Data source identifier
        destination: Data destination identifier
    
    Returns:
        Dictionary with flow results
    """
    raw_data = extract_data(source)
    transformed = transform_data(raw_data)
    count = load_data(transformed, destination)
    
    return {
        "source": source,
        "destination": destination,
        "items_processed": count
    }


if __name__ == "__main__":
    # Run locally for testing
    result = my_etl_flow(source="test", destination="test_output")
    print(f"Result: {result}")
```

### Flow with Retries and Error Handling

```python
from prefect import flow, task, get_run_logger
from prefect.tasks import task_input_hash
from datetime import timedelta


@task(
    retries=3,
    retry_delay_seconds=10,
    cache_key_fn=task_input_hash,
    cache_expiration=timedelta(hours=1)
)
def fetch_api_data(endpoint: str) -> dict:
    """Fetch data from API with retries and caching."""
    logger = get_run_logger()
    logger.info(f"Fetching from {endpoint}")
    # Your API call here
    return {"data": "example"}


@task
def process_with_fallback(data: dict) -> dict:
    """Process data with error handling."""
    logger = get_run_logger()
    try:
        # Processing logic
        return {"processed": True, **data}
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        return {"processed": False, "error": str(e)}


@flow(name="robust-flow")
def robust_flow(endpoint: str = "https://api.example.com"):
    data = fetch_api_data(endpoint)
    result = process_with_fallback(data)
    return result
```

### Flow with Subflows

```python
from prefect import flow, task


@flow(name="data-validation")
def validate_data(data: list) -> bool:
    """Subflow for data validation."""
    return len(data) > 0 and all(item is not None for item in data)


@flow(name="data-enrichment")
def enrich_data(data: list) -> list:
    """Subflow for data enrichment."""
    return [{"value": item, "enriched": True} for item in data]


@flow(name="main-pipeline")
def main_pipeline(input_data: list):
    """Main flow that orchestrates subflows."""
    if validate_data(input_data):
        enriched = enrich_data(input_data)
        return enriched
    return []
```

---

## 3. Testing Flows

### Testing in Local Docker Environment (Recommended)

Always test flows in the local Docker environment before deploying to production. This ensures your flow works in the same containerized environment as production.

#### Step 1: Start Local Environment

```bash
# Start Prefect server, PostgreSQL, and worker
./scripts/local-up.sh

# Verify all containers are running
docker compose -f docker-compose.local.yml ps
```

#### Step 2: Run Flow Against Local Server

```bash
# Set the API URL to local Prefect server
export PREFECT_API_URL=http://localhost:4200/api

# Run your flow - it will register and execute against local server
python flows/my_flow.py
```

#### Step 3: Monitor in Local Prefect UI

1. Open http://localhost:4200 in your browser
2. Go to **Flow Runs** to see your flow execution
3. Check logs, task states, and results
4. Verify the flow completed successfully

#### Step 4: Test with Local Worker

The local environment includes a worker that executes flows. To test scheduled/deployed flows:

```bash
# Register a deployment
python -c "
from flows.my_flow import my_etl_flow

my_etl_flow.serve(name='local-test-deployment')
"

# In another terminal, trigger the deployment
prefect deployment run 'my-etl-flow/local-test-deployment'
```

#### Step 5: View Logs

```bash
# View all service logs
docker compose -f docker-compose.local.yml logs -f

# View specific service logs
docker compose -f docker-compose.local.yml logs -f prefect-server
docker compose -f docker-compose.local.yml logs -f prefect-worker
```

#### Step 6: Clean Up

```bash
# Stop local environment when done
./scripts/local-down.sh
```

### Testing Workflow Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    Local Testing Workflow                    │
├─────────────────────────────────────────────────────────────┤
│  1. ./scripts/local-up.sh          # Start environment      │
│  2. export PREFECT_API_URL=...     # Set API URL            │
│  3. python flows/my_flow.py        # Run flow               │
│  4. Check http://localhost:4200    # Verify in UI           │
│  5. ./scripts/local-down.sh        # Stop environment       │
│  6. git push origin main           # Deploy to production   │
└─────────────────────────────────────────────────────────────┘
```

### Run Flow Directly (Without Docker)

For quick iteration during development, you can run flows without the full Docker environment:

```bash
# Run your flow directly (uses ephemeral Prefect)
python flows/my_flow.py
```

Note: This won't persist flow runs or show them in the UI.

### Unit Testing Flows

Create tests in `tests/unit/`:

```python
# tests/unit/test_my_flow.py
import pytest
from flows.my_flow import extract_data, transform_data, my_etl_flow


class TestMyFlow:
    def test_extract_data(self):
        result = extract_data.fn("test_source")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_transform_data(self):
        input_data = ["a", "b", "c"]
        result = transform_data.fn(input_data)
        assert result == ["A", "B", "C"]

    def test_my_etl_flow(self):
        result = my_etl_flow(source="test", destination="test_out")
        assert "items_processed" in result
        assert result["items_processed"] > 0
```

Run tests:

```bash
pytest tests/unit/test_my_flow.py -v
```

### Integration Testing

```python
# tests/integration/test_flow_execution.py
import pytest
from prefect.testing.utilities import prefect_test_harness


@pytest.fixture(autouse=True, scope="session")
def prefect_test_fixture():
    with prefect_test_harness():
        yield


def test_flow_runs_successfully():
    from flows.my_flow import my_etl_flow
    
    result = my_etl_flow(source="integration_test", destination="test_output")
    assert result["items_processed"] > 0
```

---

## 4. Deploying Flows

### Automatic Deployment (Recommended)

Flows are automatically deployed when you push to `main`:

```bash
git add flows/my_flow.py
git commit -m "Add my ETL flow"
git push origin main
```

The GitHub Actions workflow will:
1. Deploy code to the server
2. Register flows with Prefect

### Manual Deployment

To deploy flows manually to local or production:

```bash
# Set API URL for local
export PREFECT_API_URL=http://localhost:4200/api

# Or for production (via SSH tunnel)
ssh -L 4200:localhost:4200 root@prefect.raniendu.dev

# Run the flow to register it
python flows/my_flow.py
```

### Creating Scheduled Deployments

Add deployment configuration in `scripts/deploy-flows.py` inside `register_deployments`:

```python
from prefect.client.schemas.schedules import CronSchedule


# Example inside register_deployments(...)
if flow.name == "my-etl-flow":
    deployments_to_create.append({
        "name": "daily-etl",
        "schedule": CronSchedule(
            cron="0 6 * * *",
            timezone="America/Los_Angeles",
        ),
        "description": "Daily ETL pipeline",
    })
```

`flows/deployments.py` is no longer used.

---

## 5. Removing Flows

### Remove Flow File

1. Delete the flow file:
   ```bash
   rm flows/my_old_flow.py
   ```

2. Remove custom schedule logic from `scripts/deploy-flows.py` if referenced:
   ```python
   # Remove the condition that appends deployment config for this flow
   ```

3. Commit and push:
   ```bash
   git add -A
   git commit -m "Remove my_old_flow"
   git push origin main
   ```

### Remove Flow from Prefect Server

Flows remain in Prefect's database even after removing the file. To clean up:

**Via Prefect UI:**
1. Go to **Flows** page
2. Click on the flow to remove
3. Click **Delete** (if available)

**Via Prefect CLI:**
```bash
# List flows
prefect flow ls

# Delete a specific flow (by ID)
prefect flow delete <flow-id>
```

**Via API:**
```python
from prefect import get_client
import asyncio

async def delete_flow(flow_name: str):
    async with get_client() as client:
        flows = await client.read_flows(flow_filter={"name": {"any_": [flow_name]}})
        for flow in flows:
            await client.delete_flow(flow.id)
            print(f"Deleted flow: {flow.name}")

asyncio.run(delete_flow("my-old-flow"))
```

### Remove Deployments

**Via Prefect UI:**
1. Go to **Deployments** page
2. Find the deployment
3. Click **Delete**

**Via CLI:**
```bash
# List deployments
prefect deployment ls

# Delete deployment
prefect deployment delete "flow-name/deployment-name"
```

---

## 6. Best Practices

### Flow Design

- **Single Responsibility**: Each flow should do one thing well
- **Idempotency**: Flows should be safe to re-run
- **Parameters**: Use parameters for configuration, not hardcoded values
- **Logging**: Use `get_run_logger()` for structured logging

### Task Design

- **Small Tasks**: Break work into small, focused tasks
- **Retries**: Add retries for external calls (APIs, databases)
- **Caching**: Cache expensive operations when appropriate
- **Type Hints**: Use type hints for better documentation

### Error Handling

```python
from prefect import flow, task, get_run_logger
from prefect.states import Failed


@task
def risky_operation():
    # May fail
    pass


@flow
def flow_with_error_handling():
    logger = get_run_logger()
    
    try:
        result = risky_operation()
        return result
    except Exception as e:
        logger.error(f"Flow failed: {e}")
        # Return failed state or raise
        raise
```

### Naming Conventions

- **Flow names**: Use kebab-case (`my-etl-flow`)
- **Task names**: Use snake_case (`extract_data`)
- **File names**: Use snake_case (`my_flow.py`)
- **Deployment names**: Descriptive (`daily-etl`, `hourly-sync`)

### Project Organization

```
flows/
├── __init__.py
├── my_flow.py          # Project-specific flow
├── etl/                # ETL-related flows
│   ├── __init__.py
│   ├── extract.py
│   └── transform.py
├── reports/            # Reporting flows
│   ├── __init__.py
│   └── daily_report.py
└── utils/              # Shared utilities
    ├── __init__.py
    └── helpers.py
```

### Testing Strategy

1. **Unit tests**: Test individual tasks with `.fn()` method
2. **Integration tests**: Test full flow execution
3. **Property tests**: Use Hypothesis for edge cases
4. **Local testing**: Always test locally before deploying

---

## Quick Reference

### Common Commands

```bash
# Start local environment
./scripts/local-up.sh

# Stop local environment
./scripts/local-down.sh

# Run a flow
python flows/my_flow.py

# Run tests
pytest tests/

# Deploy to production
git push origin main
```

### Prefect CLI Commands

```bash
# List flows
prefect flow ls

# List deployments
prefect deployment ls

# Run a deployment
prefect deployment run "flow-name/deployment-name"

# View flow runs
prefect flow-run ls
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `PREFECT_API_URL` | Prefect server URL |
| `PREFECT_LOGGING_LEVEL` | Log level (DEBUG, INFO, WARNING, ERROR) |

---

## Additional Resources

- [Prefect Documentation](https://docs.prefect.io/)
- [Prefect Concepts](https://docs.prefect.io/concepts/)
- [Task Caching](https://docs.prefect.io/concepts/tasks/#caching)
- [Deployments](https://docs.prefect.io/concepts/deployments/)
