#!/usr/bin/env bash
set -euo pipefail

compose_file="${1:-deploy/compose/docker-compose.prod.yml}"
env_file="${2:-.env.production}"

backup_root="${POSTGRES_CONSOLIDATION_BACKUP_DIR:-/var/backups/platform/postgres-consolidation}"
marker="${POSTGRES_CONSOLIDATION_MARKER:-/var/lib/platform/postgres-consolidated}"

new_container="${PLATFORM_POSTGRES_CONTAINER:-platform-postgres}"
old_prefect_container="${PREFECT_POSTGRES_CONTAINER:-platform-prefect-postgres}"
old_airflow_container="${AIRFLOW_POSTGRES_CONTAINER:-platform-airflow-postgres}"

compose=(docker compose -f "$compose_file" --env-file "$env_file")

container_exists() {
  docker inspect "$1" >/dev/null 2>&1
}

wait_for_postgres() {
  local container="$1"
  local user="$2"
  local database="$3"

  for attempt in $(seq 1 60); do
    if docker exec "$container" pg_isready -U "$user" -d "$database" >/dev/null 2>&1; then
      return 0
    fi

    echo "Waiting for ${container}/${database}, attempt ${attempt}"
    sleep 2
  done

  docker logs --tail 120 "$container" || true
  echo "Timed out waiting for ${container}/${database}."
  return 1
}

dump_database() {
  local container="$1"
  local user="$2"
  local database="$3"
  local destination="$4"
  local remote_path="/tmp/${database}.dump"

  docker exec "$container" pg_dump -U "$user" -d "$database" -Fc -f "$remote_path"
  docker cp "${container}:${remote_path}" "$destination"
  docker exec "$container" rm -f "$remote_path"
}

restore_database() {
  local database="$1"
  local role="$2"
  local source="$3"
  local remote_path="/tmp/${database}.dump"

  docker cp "$source" "${new_container}:${remote_path}"
  docker exec "$new_container" pg_restore \
    -U postgres \
    -d "$database" \
    --clean \
    --if-exists \
    --no-owner \
    --role="$role" \
    "$remote_path"
  docker exec "$new_container" rm -f "$remote_path"
}

write_marker() {
  local mode="$1"
  local backup_dir="${2:-}"

  mkdir -p "$(dirname "$marker")"
  {
    printf 'mode=%s\n' "$mode"
    printf 'completed_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    if [ -n "$backup_dir" ]; then
      printf 'backup_dir=%s\n' "$backup_dir"
    fi
  } > "$marker"
}

if [ -f "$marker" ]; then
  echo "Shared Postgres migration marker exists at ${marker}; skipping."
  exit 0
fi

old_prefect_exists=0
old_airflow_exists=0
container_exists "$old_prefect_container" && old_prefect_exists=1
container_exists "$old_airflow_container" && old_airflow_exists=1

if [ "$old_prefect_exists" -eq 0 ] && [ "$old_airflow_exists" -eq 0 ]; then
  if container_exists "$new_container"; then
    echo "Shared Postgres container exists but marker is absent; refusing to infer migration state."
    exit 1
  fi

  echo "No legacy Postgres containers found; initializing shared Postgres for a new host."
  "${compose[@]}" up -d postgres
  wait_for_postgres "$new_container" postgres postgres
  wait_for_postgres "$new_container" prefect prefect
  wait_for_postgres "$new_container" airflow airflow
  write_marker fresh
  exit 0
fi

if [ "$old_prefect_exists" -ne 1 ] || [ "$old_airflow_exists" -ne 1 ]; then
  echo "Expected both legacy Postgres containers or neither; found prefect=${old_prefect_exists}, airflow=${old_airflow_exists}."
  exit 1
fi

if container_exists "$new_container"; then
  echo "Shared Postgres container exists but marker is absent; refusing to overwrite it."
  exit 1
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="${backup_root}/${timestamp}"
mkdir -p "$backup_dir"

echo "Stopping app containers before database dumps."
docker stop \
  platform-prefect-worker \
  platform-prefect-server \
  platform-airflow-scheduler \
  platform-airflow-webserver \
  platform-airflow-init >/dev/null 2>&1 || true

docker start "$old_prefect_container" "$old_airflow_container" >/dev/null
wait_for_postgres "$old_prefect_container" prefect prefect
wait_for_postgres "$old_airflow_container" airflow airflow

echo "Dumping legacy Prefect and Airflow databases."
dump_database "$old_prefect_container" prefect prefect "${backup_dir}/prefect.dump"
dump_database "$old_airflow_container" airflow airflow "${backup_dir}/airflow.dump"

echo "Starting shared Postgres."
"${compose[@]}" up -d postgres
wait_for_postgres "$new_container" postgres postgres
wait_for_postgres "$new_container" prefect prefect
wait_for_postgres "$new_container" airflow airflow

echo "Restoring Prefect and Airflow databases into shared Postgres."
restore_database prefect prefect "${backup_dir}/prefect.dump"
restore_database airflow airflow "${backup_dir}/airflow.dump"

write_marker migrated "$backup_dir"
echo "Postgres consolidation complete. Legacy dump backups are in ${backup_dir}."
