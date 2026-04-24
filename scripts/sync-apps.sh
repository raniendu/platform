#!/usr/bin/env bash
set -euo pipefail

apps=(
  "apps/dotdev"
  "apps/prefect"
  "apps/flow"
)

for app in "${apps[@]}"; do
  echo "==> uv sync --project ${app}"
  uv sync --project "${app}"
done

