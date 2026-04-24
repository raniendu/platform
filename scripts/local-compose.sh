#!/usr/bin/env bash
set -euo pipefail

command="${1:-up}"
shift || true

compose_file="deploy/compose/docker-compose.local.yml"
env_file=".env.local"

case "${command}" in
  config)
    docker compose -f "${compose_file}" --env-file "${env_file}" config "$@"
    ;;
  up)
    docker compose -f "${compose_file}" --env-file "${env_file}" up -d --build "$@"
    ;;
  ps)
    docker compose -f "${compose_file}" --env-file "${env_file}" ps "$@"
    ;;
  logs)
    docker compose -f "${compose_file}" --env-file "${env_file}" logs "$@"
    ;;
  down)
    docker compose -f "${compose_file}" --env-file "${env_file}" down "$@"
    ;;
  *)
    echo "Usage: $0 {config|up|ps|logs|down}" >&2
    exit 2
    ;;
esac

