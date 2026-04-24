#!/bin/bash
# Start local Prefect development environment
# Requirements: 1.1, 1.5
#
# Usage: ./scripts/local-up.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.local.yml"

echo "Starting local Prefect environment..."

# Start services
docker compose -f "$COMPOSE_FILE" up -d

echo "Waiting for Prefect server to be healthy..."

# Wait for Prefect server to be healthy (max 60 seconds)
MAX_WAIT=60
WAIT_INTERVAL=2
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    if docker compose -f "$COMPOSE_FILE" ps prefect-server | grep -q "healthy"; then
        echo ""
        echo "✓ Prefect server is healthy!"
        echo ""
        echo "Prefect UI available at: http://localhost:4200"
        echo "Prefect API available at: http://localhost:4200/api"
        echo ""
        echo "To stop the environment, run: ./scripts/local-down.sh"
        exit 0
    fi
    
    printf "."
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

echo ""
echo "⚠ Warning: Prefect server did not become healthy within ${MAX_WAIT}s"
echo "Check logs with: docker compose -f docker-compose.local.yml logs prefect-server"
exit 1
