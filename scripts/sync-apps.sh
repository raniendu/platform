#!/usr/bin/env bash
set -euo pipefail

apps=(
  "apps/dotdev"
  "apps/prefect"
  "apps/flow"
)

for app in "${apps[@]}"; do
  if (($#)); then
    echo "==> uv sync --project ${app} $*"
  else
    echo "==> uv sync --project ${app}"
  fi
  uv sync --project "${app}" "$@"
done
