#!/bin/bash
# Stop local Prefect development environment
# Requirements: 1.5
#
# Usage: ./scripts/local-down.sh
#
# This script stops all containers but preserves data volumes.
# To remove volumes as well, use: docker compose -f docker-compose.local.yml down -v

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.local.yml"

echo "Stopping local Prefect environment..."

# Stop and remove containers (preserve volumes)
docker compose -f "$COMPOSE_FILE" down

echo "✓ Local environment stopped"
echo ""
echo "Note: Data volumes are preserved. To remove them, run:"
echo "  docker compose -f docker-compose.local.yml down -v"
