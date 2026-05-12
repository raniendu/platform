#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$APP_DIR/../.." && pwd)"

ENV_FILE="${RAMAN_ENV_FILE:-$ROOT_DIR/.env.local}"
HOST="${RAMAN_LOCAL_HOST:-127.0.0.1}"
PORT="${RAMAN_LOCAL_PORT:-8000}"
STATE_DIR="${RAMAN_LOCAL_DEBUG_STATE_DIR:-$APP_DIR/.raman/prod-debug}"

if [[ ! -f "$ENV_FILE" ]]; then
  printf 'Missing env file: %s\n' "$ENV_FILE" >&2
  printf 'Set RAMAN_ENV_FILE or create root .env.local with Raman secrets.\n' >&2
  exit 1
fi

set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a

if [[ -z "${DO_INFERENCE_API_KEY:-}" ]]; then
  printf 'DO_INFERENCE_API_KEY is required for local prod-debug mode.\n' >&2
  exit 1
fi

mkdir -p "$STATE_DIR"

export RAMAN_MODEL_PROVIDER="${RAMAN_LOCAL_DEBUG_PROVIDER:-digitalocean}"
export RAMAN_DEV_MODEL="${RAMAN_LOCAL_DEBUG_MODEL:-gemma-4-31B-it}"
export DO_INFERENCE_BASE_URL="${RAMAN_LOCAL_DEBUG_DO_BASE_URL:-${DO_INFERENCE_BASE_URL:-https://inference.do-ai.run/v1}}"
export RAMAN_LOG_LEVEL="${RAMAN_LOCAL_DEBUG_LOG_LEVEL:-DEBUG}"
export RAMAN_DB_PATH="${RAMAN_LOCAL_DEBUG_RAMAN_DB_PATH:-$STATE_DIR/raman.sqlite3}"
export DBOS_SYSTEM_DATABASE_URL="${RAMAN_LOCAL_DEBUG_DBOS_URL:-sqlite:///$STATE_DIR/dbos.sqlite3}"

printf 'Starting Raman local prod-debug on http://%s:%s\n' "$HOST" "$PORT"
printf 'Model provider: %s\n' "$RAMAN_MODEL_PROVIDER"
printf 'Model: %s\n' "$RAMAN_DEV_MODEL"
printf 'Logs: stdout from this terminal\n'

exec uv run --project "$APP_DIR" --locked uvicorn raman.api:app --host "$HOST" --port "$PORT"
