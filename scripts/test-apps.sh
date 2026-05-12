#!/usr/bin/env bash
set -euo pipefail

uv run --project apps/dotdev pytest apps/dotdev/tests -q
uv run --project apps/raman pytest apps/raman/tests -q
uv run --project apps/homi pytest apps/homi/tests -q
uv run --project apps/vikram pytest apps/vikram/tests -q
uv run --project apps/prefect pytest apps/prefect/tests/property/
uv run --project apps/flow python apps/flow/scripts/validate-dags.py
uv run --project apps/flow pytest apps/flow/tests/
