#!/bin/bash
# Prefect worker startup script
# Requirements: 7.3, 7.4
#
# This script:
# 1. Configures the Prefect API URL to connect to the server
# 2. Creates the work pool if it doesn't exist
# 3. Starts the worker to execute flows
#
# The worker polls the work pool for scheduled flow runs and executes them
# using the process work pool type (runs flows as subprocesses)

set -e

PREFECT_API_URL="${PREFECT_API_URL:-http://prefect-server:4200/api}"
WORK_POOL_NAME="${WORK_POOL_NAME:-default-pool}"
WORK_POOL_TYPE="${WORK_POOL_TYPE:-process}"

echo "### Prefect Worker Startup"
echo "### API URL: $PREFECT_API_URL"
echo "### Work Pool: $WORK_POOL_NAME"
echo "### Work Pool Type: $WORK_POOL_TYPE"

# Configure Prefect API URL
echo "### Configuring Prefect API URL"
prefect config set PREFECT_API_URL="$PREFECT_API_URL"

# Wait for Prefect server to be ready
echo "### Waiting for Prefect server to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0
until python -c "import urllib.request; urllib.request.urlopen('$PREFECT_API_URL/health')" > /dev/null 2>&1; do
  RETRY_COUNT=$((RETRY_COUNT + 1))
  if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
    echo "### ERROR: Prefect server not ready after $MAX_RETRIES attempts"
    exit 1
  fi
  echo "### Waiting for Prefect server... (attempt $RETRY_COUNT/$MAX_RETRIES)"
  sleep 2
done

echo "### Prefect server is ready"

echo "### Verifying flow dependencies"
python -c "import httpx; from dotenv import load_dotenv; from google import genai"

# Create work pool if it doesn't exist
echo "### Ensuring work pool '$WORK_POOL_NAME' exists"
if ! prefect work-pool inspect "$WORK_POOL_NAME" > /dev/null 2>&1; then
  echo "### Creating work pool '$WORK_POOL_NAME' of type '$WORK_POOL_TYPE'"
  prefect work-pool create "$WORK_POOL_NAME" --type "$WORK_POOL_TYPE"
else
  echo "### Work pool '$WORK_POOL_NAME' already exists"
fi

# Start the worker
echo "### Starting Prefect worker"
echo "### Worker will poll for flow runs from work pool '$WORK_POOL_NAME'"
exec prefect worker start --pool "$WORK_POOL_NAME" --type "$WORK_POOL_TYPE"
