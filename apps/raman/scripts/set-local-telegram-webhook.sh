#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$APP_DIR/../.." && pwd)"

ENV_FILE="${RAMAN_ENV_FILE:-$ROOT_DIR/.env.local}"

if [[ ! -f "$ENV_FILE" ]]; then
  printf 'Missing env file: %s\n' "$ENV_FILE" >&2
  printf 'Set RAMAN_ENV_FILE or create root .env.local with Telegram secrets.\n' >&2
  exit 1
fi

exec uv run --project "$APP_DIR" --locked python -m raman.local_webhook --env-file "$ENV_FILE" "$@"
