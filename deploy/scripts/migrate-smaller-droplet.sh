#!/usr/bin/env bash
set -euo pipefail

OLD_DROPLET_NAME="${OLD_DROPLET_NAME:-platform-shared}"
NEW_DROPLET_NAME="${NEW_DROPLET_NAME:-platform-shared-small}"
TARGET_DROPLET_SIZE="${TARGET_DROPLET_SIZE:-s-1vcpu-2gb}"
TARGET_REGION="${TARGET_REGION:-nyc3}"
FIREWALL_NAME="${FIREWALL_NAME:-${OLD_DROPLET_NAME}-firewall}"
MIGRATION_PHASE="${MIGRATION_PHASE:?MIGRATION_PHASE is required}"
MIGRATION_CONFIRMATION="${MIGRATION_CONFIRMATION:?MIGRATION_CONFIRMATION is required}"
PLATFORM_SSH_USER="${PLATFORM_SSH_USER:-root}"
PLATFORM_SSH_PORT="${PLATFORM_SSH_PORT:-22}"
SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/platform_key}"
COMPOSE_FILE="${COMPOSE_FILE:-deploy/compose/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"
TF_WORKING_DIR="${TF_WORKING_DIR:-infra/terraform}"

RUNNER_SSH_CIDR=""
REMOTE_DOCKER_CONFIG=""
STAGE_WRITERS_STOPPED=0
STAGE_KEEP_WRITERS_STOPPED=0
TMP_DIR=""

log() {
  printf '%s\n' "$*" >&2
}

error() {
  printf '::error::%s\n' "$*" >&2
  exit 1
}

summary() {
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    printf '%s\n' "$*" >> "$GITHUB_STEP_SUMMARY"
  fi
}

require_actions() {
  if [ "${GITHUB_ACTIONS:-}" != "true" ]; then
    error "This migration performs DigitalOcean writes and must run from GitHub Actions."
  fi
}

require_tool() {
  command -v "$1" >/dev/null 2>&1 || error "Missing required tool: $1"
}

require_env() {
  local name="$1"
  if [ -z "${!name:-}" ]; then
    error "${name} is required"
  fi
}

validate_confirmation() {
  case "$MIGRATION_PHASE" in
    stage)
      [ "$MIGRATION_CONFIRMATION" = "stage-platform-shared-to-s-1vcpu-2gb" ] ||
        error "Confirmation must be stage-platform-shared-to-s-1vcpu-2gb"
      ;;
    promote)
      [ "$MIGRATION_CONFIRMATION" = "promote-platform-shared-small-to-platform-shared" ] ||
        error "Confirmation must be promote-platform-shared-small-to-platform-shared"
      ;;
    rollback_stage)
      [ "$MIGRATION_CONFIRMATION" = "rollback-platform-shared-small" ] ||
        error "Confirmation must be rollback-platform-shared-small"
      ;;
    decommission_retired)
      require_env RETIRED_DROPLET_NAME
      [ "$MIGRATION_CONFIRMATION" = "decommission-${RETIRED_DROPLET_NAME}" ] ||
        error "Confirmation must be decommission-${RETIRED_DROPLET_NAME}"
      case "$RETIRED_DROPLET_NAME" in
        "${OLD_DROPLET_NAME}-retired-"*) ;;
        *) error "RETIRED_DROPLET_NAME must start with ${OLD_DROPLET_NAME}-retired-" ;;
      esac
      ;;
    *)
      error "Unsupported MIGRATION_PHASE: ${MIGRATION_PHASE}"
      ;;
  esac
}

droplet_lines_by_name() {
  local name="$1"
  doctl compute droplet list --format ID,Name,Status,SizeSlug,PublicIPv4 --no-header |
    awk -v expected="$name" '$2 == expected {print $0}'
}

droplet_count_by_name() {
  local name="$1"
  droplet_lines_by_name "$name" | sed '/^$/d' | wc -l | tr -d ' '
}

require_one_droplet() {
  local name="$1"
  mapfile -t rows < <(droplet_lines_by_name "$name")
  if [ "${#rows[@]}" -ne 1 ]; then
    printf '%s\n' "${rows[@]}" >&2
    error "Expected exactly one Droplet named ${name}, found ${#rows[@]}"
  fi
  printf '%s\n' "${rows[0]}"
}

read_droplet() {
  local line="$1"
  local -n _id="$2"
  local -n _name="$3"
  local -n _status="$4"
  local -n _size="$5"
  local -n _ip="$6"
  read -r _id _name _status _size _ip <<< "$line"
  [ -n "$_id" ] || error "Could not parse Droplet ID from: ${line}"
  [ -n "$_ip" ] || error "Could not parse public IP from: ${line}"
}

require_one_firewall() {
  local name="$1"
  mapfile -t rows < <(doctl compute firewall list --format ID,Name --no-header | awk -v expected="$name" '$2 == expected {print $1}')
  if [ "${#rows[@]}" -ne 1 ]; then
    printf '%s\n' "${rows[@]}" >&2
    error "Expected exactly one firewall named ${name}, found ${#rows[@]}"
  fi
  printf '%s\n' "${rows[0]}"
}

ssh_key_csv() {
  require_env TF_VAR_ssh_key_fingerprints
  printf '%s' "$TF_VAR_ssh_key_fingerprints" |
    jq -er 'if type == "array" and length > 0 then join(",") else error("empty SSH key list") end'
}

create_new_droplet() {
  local ssh_keys
  ssh_keys="$(ssh_key_csv)"

  doctl compute droplet create "$NEW_DROPLET_NAME" \
    --region "$TARGET_REGION" \
    --size "$TARGET_DROPLET_SIZE" \
    --image ubuntu-24-04-x64 \
    --ssh-keys "$ssh_keys" \
    --tag-names "platform,shared-runtime,smaller-droplet-migration" \
    --enable-backups \
    --backup-policy-plan weekly \
    --backup-policy-weekday SUN \
    --backup-policy-hour 4 \
    --enable-monitoring \
    --enable-private-networking \
    --user-data-file "${TF_WORKING_DIR}/cloud-init.yaml" \
    --wait
}

wait_for_new_droplet_ip() {
  local line id name status size ip

  for _ in $(seq 1 30); do
    line="$(require_one_droplet "$NEW_DROPLET_NAME")"
    read_droplet "$line" id name status size ip
    if [ "$status" = "active" ] && [ -n "$ip" ] && [ "$ip" != "<nil>" ]; then
      printf '%s\n' "$line"
      return 0
    fi
    sleep 10
  done

  error "New Droplet did not become active with a public IPv4 address"
}

open_runner_ssh() {
  local firewall_id="$1"
  local runner_ip

  runner_ip="$(curl -fsS https://api.ipify.org)"
  RUNNER_SSH_CIDR="${runner_ip}/32"

  doctl compute firewall remove-rules "$firewall_id" \
    --inbound-rules "protocol:tcp,ports:22,address:${RUNNER_SSH_CIDR}" >/dev/null 2>&1 || true
  doctl compute firewall add-rules "$firewall_id" \
    --inbound-rules "protocol:tcp,ports:22,address:${RUNNER_SSH_CIDR}"
}

close_runner_ssh() {
  local firewall_id="${1:-}"

  if [ -n "$firewall_id" ] && [ -n "$RUNNER_SSH_CIDR" ]; then
    doctl compute firewall remove-rules "$firewall_id" \
      --inbound-rules "protocol:tcp,ports:22,address:${RUNNER_SSH_CIDR}" || true
  fi
}

ssh_base_opts() {
  printf '%s\n' \
    -i "$SSH_KEY_PATH" \
    -p "$PLATFORM_SSH_PORT" \
    -o ConnectTimeout=10 \
    -o StrictHostKeyChecking=yes
}

add_known_host() {
  local host="$1"

  mkdir -p "$HOME/.ssh"
  chmod 700 "$HOME/.ssh"
  ssh-keygen -R "[${host}]:${PLATFORM_SSH_PORT}" >/dev/null 2>&1 || true
  ssh-keyscan -p "$PLATFORM_SSH_PORT" "$host" >> "$HOME/.ssh/known_hosts"
}

ssh_host() {
  local host="$1"
  shift

  ssh -i "$SSH_KEY_PATH" -p "$PLATFORM_SSH_PORT" \
    -o ConnectTimeout=10 \
    -o StrictHostKeyChecking=yes \
    "${PLATFORM_SSH_USER}@${host}" "$@"
}

scp_to_host() {
  local src="$1"
  local host="$2"
  local dest="$3"

  scp -i "$SSH_KEY_PATH" -P "$PLATFORM_SSH_PORT" \
    -o StrictHostKeyChecking=yes \
    "$src" "${PLATFORM_SSH_USER}@${host}:${dest}"
}

wait_for_bootstrap() {
  local host="$1"

  for attempt in $(seq 1 60); do
    if ssh_host "$host" "cloud-init status --wait >/dev/null 2>&1 || true; docker version >/dev/null 2>&1 && test -d /opt/platform"; then
      return 0
    fi
    log "Waiting for ${host} bootstrap, attempt ${attempt}"
    sleep 10
  done

  error "Droplet bootstrap did not finish for ${host}"
}

validate_platform_env() {
  require_env PLATFORM_ENV_FILE
  require_env DOTDEV_IMAGE
  require_env PREFECT_IMAGE
  require_env AIRFLOW_IMAGE
  require_env RAMAN_IMAGE
  require_env RAMAN_MODEL_PROVIDER
  require_env RAMAN_DEV_MODEL
  require_env RAMAN_AGENT
  require_env RAMAN_PUBLIC_BASE_URL
  require_env DO_INFERENCE_API_KEY
  require_env TELEGRAM_BOT_TOKEN
  require_env TELEGRAM_WEBHOOK_SECRET
  require_env TELEGRAM_ALLOWED_CHAT_IDS
  require_env GOBIND_TELEGRAM_BOT_TOKEN
  require_env GOBIND_TELEGRAM_WEBHOOK_SECRET
  require_env GOBIND_TELEGRAM_ALLOWED_CHAT_IDS
  require_env LEO_TELEGRAM_BOT_TOKEN
  require_env LEO_TELEGRAM_WEBHOOK_SECRET
  require_env LEO_TELEGRAM_ALLOWED_CHAT_IDS

  for key in PLATFORM_POSTGRES_PASSWORD PREFECT_POSTGRES_PASSWORD AIRFLOW_POSTGRES_PASSWORD; do
    if ! printf '%s\n' "$PLATFORM_ENV_FILE" | grep -Eq "^${key}="; then
      error "PLATFORM_ENV_FILE must include ${key}"
    fi
  done
}

upload_repository() {
  local host="$1"
  local ssh_cmd

  ssh_cmd="ssh -i ${SSH_KEY_PATH} -p ${PLATFORM_SSH_PORT} -o StrictHostKeyChecking=yes"
  rsync -az --delete \
    --exclude '.git/' \
    --exclude '.github/' \
    --exclude '.env*' \
    --exclude '**/.venv/' \
    --exclude '**/.pytest_cache/' \
    --exclude '**/__pycache__/' \
    -e "$ssh_cmd" \
    ./ "${PLATFORM_SSH_USER}@${host}:/opt/platform/"
}

upload_production_env() {
  local host="$1"

  {
    printf '%s\n' "$PLATFORM_ENV_FILE"
    printf 'DOTDEV_IMAGE=%s\n' "$DOTDEV_IMAGE"
    printf 'PREFECT_IMAGE=%s\n' "$PREFECT_IMAGE"
    printf 'AIRFLOW_IMAGE=%s\n' "$AIRFLOW_IMAGE"
    printf 'RAMAN_IMAGE=%s\n' "$RAMAN_IMAGE"
    printf 'RAMAN_MODEL_PROVIDER=%s\n' "$RAMAN_MODEL_PROVIDER"
    printf 'RAMAN_DEV_MODEL=%s\n' "$RAMAN_DEV_MODEL"
    printf 'RAMAN_AGENT=%s\n' "$RAMAN_AGENT"
    printf 'RAMAN_PUBLIC_BASE_URL=%s\n' "$RAMAN_PUBLIC_BASE_URL"
    printf 'DO_INFERENCE_API_KEY=%s\n' "$DO_INFERENCE_API_KEY"
    printf 'PARALLEL_API_KEY=%s\n' "${PARALLEL_API_KEY:-}"
  } | ssh_host "$host" "cat > /opt/platform/${ENV_FILE} && chmod 600 /opt/platform/${ENV_FILE}"
  {
    printf 'TELEGRAM_BOT_TOKEN=%s\n' "$TELEGRAM_BOT_TOKEN"
    printf 'TELEGRAM_WEBHOOK_SECRET=%s\n' "$TELEGRAM_WEBHOOK_SECRET"
    printf 'TELEGRAM_ALLOWED_CHAT_IDS=%s\n' "$TELEGRAM_ALLOWED_CHAT_IDS"
    printf 'TELEGRAM_BOT_USERNAME=%s\n' "${TELEGRAM_BOT_USERNAME:-}"
    printf 'GOBIND_TELEGRAM_BOT_TOKEN=%s\n' "$GOBIND_TELEGRAM_BOT_TOKEN"
    printf 'GOBIND_TELEGRAM_WEBHOOK_SECRET=%s\n' "$GOBIND_TELEGRAM_WEBHOOK_SECRET"
    printf 'GOBIND_TELEGRAM_ALLOWED_CHAT_IDS=%s\n' "$GOBIND_TELEGRAM_ALLOWED_CHAT_IDS"
    printf 'GOBIND_TELEGRAM_BOT_USERNAME=%s\n' "${GOBIND_TELEGRAM_BOT_USERNAME:-}"
    printf 'LEO_TELEGRAM_BOT_TOKEN=%s\n' "$LEO_TELEGRAM_BOT_TOKEN"
    printf 'LEO_TELEGRAM_WEBHOOK_SECRET=%s\n' "$LEO_TELEGRAM_WEBHOOK_SECRET"
    printf 'LEO_TELEGRAM_ALLOWED_CHAT_IDS=%s\n' "$LEO_TELEGRAM_ALLOWED_CHAT_IDS"
    printf 'LEO_TELEGRAM_BOT_USERNAME=%s\n' "${LEO_TELEGRAM_BOT_USERNAME:-}"
  } | ssh_host "$host" "cat > /opt/platform/.env.raman && chmod 600 /opt/platform/.env.raman"
}

upload_ghcr_credentials() {
  local host="$1"

  REMOTE_DOCKER_CONFIG="/tmp/platform-ghcr-${GITHUB_RUN_ID:-manual}-${GITHUB_RUN_ATTEMPT:-1}"
  ssh_host "$host" "mkdir -p '${REMOTE_DOCKER_CONFIG}' && chmod 700 '${REMOTE_DOCKER_CONFIG}'"
  scp_to_host "$HOME/.docker/config.json" "$host" "${REMOTE_DOCKER_CONFIG}/config.json"
  ssh_host "$host" "chmod 600 '${REMOTE_DOCKER_CONFIG}/config.json'"
}

remove_remote_ghcr_credentials() {
  local host="${1:-}"

  if [ -n "$host" ] && [ -n "$REMOTE_DOCKER_CONFIG" ]; then
    ssh_host "$host" "rm -rf '${REMOTE_DOCKER_CONFIG}'" || true
  fi
}

stop_new_runtime_stack() {
  local host="$1"

  ssh_host "$host" "cd /opt/platform && docker compose -f ${COMPOSE_FILE} --env-file ${ENV_FILE} stop caddy dotdev prefect-server prefect-worker airflow-webserver airflow-scheduler airflow-init raman || true"
}

stop_old_writers() {
  local host="$1"

  ssh_host "$host" "cd /opt/platform && docker compose -f ${COMPOSE_FILE} --env-file ${ENV_FILE} stop prefect-server prefect-worker airflow-webserver airflow-scheduler airflow-init raman || true"
  STAGE_WRITERS_STOPPED=1
}

start_old_stack() {
  local host="$1"

  ssh_host "$host" "cd /opt/platform && docker compose -f ${COMPOSE_FILE} --env-file ${ENV_FILE} up -d --no-build"
}

ensure_old_writers_stopped() {
  local host="$1"
  local running

  running="$(ssh_host "$host" 'for container in platform-prefect-server platform-prefect-worker platform-airflow-webserver platform-airflow-scheduler platform-airflow-init platform-raman; do status=$(docker inspect -f "{{.State.Status}}" "$container" 2>/dev/null || true); if [ "$status" = running ]; then echo "$container"; fi; done')"
  if [ -n "$running" ]; then
    printf '%s\n' "$running" >&2
    error "Old writer containers are running. Rerun stage before promote, or rollback the staged migration."
  fi
}

ensure_old_postgres_consolidated() {
  local host="$1"

  if ! ssh_host "$host" "docker inspect platform-postgres >/dev/null 2>&1"; then
    error "Old Droplet does not have platform-postgres. Run Deploy with Postgres consolidation before staging the smaller Droplet."
  fi
}

dump_database() {
  local host="$1"
  local db="$2"
  local outfile="$3"

  ssh_host "$host" "docker exec platform-postgres pg_dump -U postgres --format=custom --no-owner -d ${db}" > "$outfile"
}

dump_caddy_volume() {
  local host="$1"
  local volume_path="$2"
  local outfile="$3"

  ssh_host "$host" "docker exec platform-caddy tar -C ${volume_path} -czf - ." > "$outfile"
}

dump_docker_volume() {
  local host="$1"
  local volume="$2"
  local outfile="$3"
  local empty_dir

  if ssh_host "$host" "docker volume inspect '${volume}' >/dev/null 2>&1"; then
    ssh_host "$host" "docker pull caddy:2.8-alpine >/dev/null && docker run --rm -v '${volume}:/volume:ro' caddy:2.8-alpine tar -C /volume -czf - ." > "$outfile"
    return
  fi

  empty_dir="$(mktemp -d)"
  tar -C "$empty_dir" -czf "$outfile" .
  rmdir "$empty_dir"
}

restore_caddy_volume() {
  local host="$1"
  local volume="$2"
  local archive="$3"

  ssh_host "$host" "docker pull caddy:2.8-alpine >/dev/null"
  ssh_host "$host" "docker volume create '${volume}' >/dev/null"
  ssh_host "$host" "docker run --rm -i -v '${volume}:/volume' caddy:2.8-alpine sh -c 'find /volume -mindepth 1 -exec rm -rf {} +; tar -C /volume -xzf -'" < "$archive"
}

pull_production_images() {
  local host="$1"

  ssh_host "$host" "cd /opt/platform && docker --config '${REMOTE_DOCKER_CONFIG}' compose -f ${COMPOSE_FILE} --env-file ${ENV_FILE} pull postgres dotdev prefect-server prefect-worker airflow-init airflow-webserver airflow-scheduler raman caddy"
}

start_new_postgres() {
  local host="$1"

  ssh_host "$host" "cd /opt/platform && docker compose -f ${COMPOSE_FILE} --env-file ${ENV_FILE} up -d --no-build postgres"
  wait_container_health "$host" platform-postgres
}

show_container_logs() {
  local host="$1"
  local container="$2"

  log "Last logs for ${container} on ${host}:"
  ssh_host "$host" "docker logs --tail 200 '${container}' 2>&1" || true
}

require_container_exit_success() {
  local host="$1"
  local container="$2"
  local exit_code

  exit_code="$(ssh_host "$host" "docker inspect -f '{{.State.ExitCode}}' '${container}' 2>/dev/null || printf 'missing'")"
  if [ "$exit_code" != "0" ]; then
    show_container_logs "$host" "$container"
    error "${container} exited with code ${exit_code}"
  fi
}

restore_database() {
  local host="$1"
  local db="$2"
  local owner="$3"
  local dump_file="$4"

  scp_to_host "$dump_file" "$host" "/tmp/${db}.dump"
  ssh_host "$host" bash -se <<EOF
set -euo pipefail
docker cp /tmp/${db}.dump platform-postgres:/tmp/${db}.dump
docker exec platform-postgres psql -v ON_ERROR_STOP=1 -U postgres -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${db}';"
docker exec platform-postgres psql -v ON_ERROR_STOP=1 -U postgres -d postgres -c "DROP DATABASE IF EXISTS ${db} WITH (FORCE);"
docker exec platform-postgres psql -v ON_ERROR_STOP=1 -U postgres -d postgres -c "CREATE DATABASE ${db} OWNER ${owner};"
docker exec platform-postgres pg_restore -U postgres --no-owner --role=${owner} -d ${db} /tmp/${db}.dump
docker exec platform-postgres rm -f /tmp/${db}.dump
rm -f /tmp/${db}.dump
EOF
}

start_new_stack() {
  local host="$1"

  ssh_host "$host" "cd /opt/platform && docker --config '${REMOTE_DOCKER_CONFIG}' compose -f ${COMPOSE_FILE} --env-file ${ENV_FILE} up -d --no-build dotdev"
  if ! ssh_host "$host" "cd /opt/platform && docker --config '${REMOTE_DOCKER_CONFIG}' compose -f ${COMPOSE_FILE} --env-file ${ENV_FILE} up --no-build --force-recreate airflow-init"; then
    show_container_logs "$host" platform-airflow-init
    return 1
  fi
  require_container_exit_success "$host" platform-airflow-init
  ssh_host "$host" "cd /opt/platform && docker --config '${REMOTE_DOCKER_CONFIG}' compose -f ${COMPOSE_FILE} --env-file ${ENV_FILE} up -d --no-build prefect-server"
  wait_container_health "$host" platform-prefect-server
  ssh_host "$host" "cd /opt/platform && docker --config '${REMOTE_DOCKER_CONFIG}' compose -f ${COMPOSE_FILE} --env-file ${ENV_FILE} up -d --no-build raman"
  wait_container_health "$host" platform-raman
  ssh_host "$host" "cd /opt/platform && docker --config '${REMOTE_DOCKER_CONFIG}' compose -f ${COMPOSE_FILE} --env-file ${ENV_FILE} up -d --no-build prefect-worker airflow-webserver airflow-scheduler caddy"
}

wait_container_health() {
  local host="$1"
  local container="$2"
  local status

  for attempt in $(seq 1 60); do
    status="$(ssh_host "$host" "docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' '${container}' 2>/dev/null || true")"
    if [ "$status" = "healthy" ] || [ "$status" = "running" ]; then
      return 0
    fi
    log "Waiting for ${container} health on ${host}, attempt ${attempt}: ${status:-missing}"
    sleep 10
  done

  show_container_logs "$host" "$container"
  error "${container} did not become healthy on ${host}"
}

check_resolved_status() {
  local label="$1"
  local host="$2"
  local url="$3"
  local expected="$4"
  local ip="$5"
  local status

  for attempt in $(seq 1 24); do
    status="$(curl -sS --connect-timeout 5 --max-time 20 --resolve "${host}:443:${ip}" -o /dev/null -w '%{http_code}' "$url" || true)"
    if [ "$status" = "$expected" ]; then
      log "${label} -> ${status}"
      return 0
    fi
    log "${label} attempt ${attempt} -> ${status:-curl failed}; expected ${expected}"
    sleep 5
  done

  error "${label} did not return ${expected}"
}

check_public_status() {
  local label="$1"
  local url="$2"
  local expected="$3"
  local status

  for attempt in $(seq 1 24); do
    status="$(curl -sS --connect-timeout 5 --max-time 20 -o /dev/null -w '%{http_code}' "$url" || true)"
    if [ "$status" = "$expected" ]; then
      log "${label} -> ${status}"
      return 0
    fi
    log "${label} attempt ${attempt} -> ${status:-curl failed}; expected ${expected}"
    sleep 5
  done

  error "${label} did not return ${expected}"
}

check_public_smoke() {
  check_public_status "raniendu.dev" "https://raniendu.dev/" "200"
  check_public_status "www.raniendu.dev" "https://www.raniendu.dev/" "301"
  check_public_status "prefect.raniendu.dev/api/health" "https://prefect.raniendu.dev/api/health" "401"
  check_public_status "raman.raniendu.dev/healthz" "https://raman.raniendu.dev/healthz" "200"
  check_public_status "flow.raniendu.dev" "https://flow.raniendu.dev/" "200"
}

check_new_host_smoke() {
  local ip="$1"

  check_resolved_status "raniendu.dev on new Droplet" "raniendu.dev" "https://raniendu.dev/" "200" "$ip"
  check_resolved_status "www.raniendu.dev on new Droplet" "www.raniendu.dev" "https://www.raniendu.dev/" "301" "$ip"
  check_resolved_status "prefect.raniendu.dev/api/health on new Droplet" "prefect.raniendu.dev" "https://prefect.raniendu.dev/api/health" "401" "$ip"
  check_resolved_status "raman.raniendu.dev/healthz on new Droplet" "raman.raniendu.dev" "https://raman.raniendu.dev/healthz" "200" "$ip"
  check_resolved_status "flow.raniendu.dev on new Droplet" "flow.raniendu.dev" "https://flow.raniendu.dev/" "200" "$ip"
}

resolved_public_ip() {
  curl -sS --connect-timeout 5 --max-time 20 -o /dev/null -w '%{remote_ip}' "https://raniendu.dev/" || true
}

cleanup() {
  local status="$1"

  if [ "$MIGRATION_PHASE" = "stage" ]; then
    if [ -n "${NEW_IP:-}" ]; then
      remove_remote_ghcr_credentials "$NEW_IP"
    fi
    if [ "$status" -ne 0 ] && [ "$STAGE_WRITERS_STOPPED" = "1" ] && [ "$STAGE_KEEP_WRITERS_STOPPED" = "0" ] && [ -n "${OLD_IP:-}" ]; then
      log "Stage failed; restarting the old production stack."
      start_old_stack "$OLD_IP" || true
    fi
  fi

  if [ -n "${FIREWALL_ID:-}" ]; then
    close_runner_ssh "$FIREWALL_ID"
  fi

  if [ -n "$TMP_DIR" ]; then
    rm -rf "$TMP_DIR"
  fi
}

phase_stage() {
  local old_line new_line new_count
  local old_id old_name old_status old_size
  local new_id new_name new_status new_size

  validate_platform_env
  TMP_DIR="$(mktemp -d)"

  old_line="$(require_one_droplet "$OLD_DROPLET_NAME")"
  read_droplet "$old_line" old_id old_name old_status old_size OLD_IP
  [ "$old_status" = "active" ] || error "Old Droplet must be active, found ${old_status}"

  new_count="$(droplet_count_by_name "$NEW_DROPLET_NAME")"
  if [ "$new_count" = "0" ]; then
    log "Creating ${NEW_DROPLET_NAME} as ${TARGET_DROPLET_SIZE}."
    create_new_droplet
  elif [ "$new_count" != "1" ]; then
    error "Expected zero or one Droplet named ${NEW_DROPLET_NAME}, found ${new_count}"
  else
    log "Reusing existing ${NEW_DROPLET_NAME}."
  fi

  new_line="$(wait_for_new_droplet_ip)"
  read_droplet "$new_line" new_id new_name new_status new_size NEW_IP
  [ "$new_size" = "$TARGET_DROPLET_SIZE" ] || error "${NEW_DROPLET_NAME} is ${new_size}, expected ${TARGET_DROPLET_SIZE}"

  FIREWALL_ID="$(require_one_firewall "$FIREWALL_NAME")"
  doctl compute firewall add-droplets "$FIREWALL_ID" --droplet-ids "$new_id" || true
  open_runner_ssh "$FIREWALL_ID"

  add_known_host "$OLD_IP"
  add_known_host "$NEW_IP"
  wait_for_bootstrap "$NEW_IP"

  upload_repository "$NEW_IP"
  upload_production_env "$NEW_IP"
  upload_ghcr_credentials "$NEW_IP"
  stop_new_runtime_stack "$NEW_IP"

  ensure_old_postgres_consolidated "$OLD_IP"
  stop_old_writers "$OLD_IP"
  dump_database "$OLD_IP" prefect "${TMP_DIR}/prefect.dump"
  dump_database "$OLD_IP" airflow "${TMP_DIR}/airflow.dump"
  dump_caddy_volume "$OLD_IP" /data "${TMP_DIR}/caddy-data.tgz"
  dump_caddy_volume "$OLD_IP" /config "${TMP_DIR}/caddy-config.tgz"
  dump_docker_volume "$OLD_IP" platform_raman-state "${TMP_DIR}/raman-state.tgz"

  pull_production_images "$NEW_IP"
  restore_caddy_volume "$NEW_IP" platform_caddy-data "${TMP_DIR}/caddy-data.tgz"
  restore_caddy_volume "$NEW_IP" platform_caddy-config "${TMP_DIR}/caddy-config.tgz"
  restore_caddy_volume "$NEW_IP" platform_raman-state "${TMP_DIR}/raman-state.tgz"
  start_new_postgres "$NEW_IP"
  restore_database "$NEW_IP" prefect prefect "${TMP_DIR}/prefect.dump"
  restore_database "$NEW_IP" airflow airflow "${TMP_DIR}/airflow.dump"
  start_new_stack "$NEW_IP"

  wait_container_health "$NEW_IP" platform-postgres
  wait_container_health "$NEW_IP" platform-prefect-server
  wait_container_health "$NEW_IP" platform-raman
  wait_container_health "$NEW_IP" platform-airflow-webserver
  wait_container_health "$NEW_IP" platform-airflow-scheduler
  check_new_host_smoke "$NEW_IP"

  STAGE_KEEP_WRITERS_STOPPED=1
  summary "## Smaller Droplet staged"
  summary ""
  summary "- Old Droplet: \`${OLD_DROPLET_NAME}\` at \`${OLD_IP}\`"
  summary "- New Droplet: \`${NEW_DROPLET_NAME}\` at \`${NEW_IP}\`"
  summary "- Target size: \`${TARGET_DROPLET_SIZE}\`"
  summary ""
  summary "Next: update Squarespace A records to \`${NEW_IP}\`, verify public traffic, then rerun this workflow with phase \`promote\`."
  log "Staged ${NEW_DROPLET_NAME} at ${NEW_IP}. Old Prefect, Airflow, and Raman writers are stopped to avoid post-dump divergence."
}

phase_promote() {
  local old_line new_line old_id old_name old_status old_size new_id new_name new_status new_size current_public_ip retired_name

  old_line="$(require_one_droplet "$OLD_DROPLET_NAME")"
  new_line="$(require_one_droplet "$NEW_DROPLET_NAME")"
  read_droplet "$old_line" old_id old_name old_status old_size OLD_IP
  read_droplet "$new_line" new_id new_name new_status new_size NEW_IP
  [ "$new_size" = "$TARGET_DROPLET_SIZE" ] || error "${NEW_DROPLET_NAME} is ${new_size}, expected ${TARGET_DROPLET_SIZE}"

  FIREWALL_ID="$(require_one_firewall "$FIREWALL_NAME")"
  open_runner_ssh "$FIREWALL_ID"
  add_known_host "$OLD_IP"
  ensure_old_writers_stopped "$OLD_IP"

  current_public_ip="$(resolved_public_ip)"
  if [ "$current_public_ip" != "$NEW_IP" ]; then
    error "raniendu.dev currently reaches ${current_public_ip:-unknown}, expected new Droplet ${NEW_IP}. Update DNS before promoting."
  fi
  check_public_smoke

  retired_name="${OLD_DROPLET_NAME}-retired-${GITHUB_RUN_ID:-$(date +%Y%m%d%H%M%S)}"
  doctl compute droplet-action rename "$old_id" --droplet-name "$retired_name" --wait
  doctl compute droplet-action rename "$new_id" --droplet-name "$OLD_DROPLET_NAME" --wait

  summary "## Smaller Droplet promoted"
  summary ""
  summary "- New canonical Droplet: \`${OLD_DROPLET_NAME}\` at \`${NEW_IP}\`"
  summary "- Retired rollback Droplet: \`${retired_name}\` at \`${OLD_IP}\`"
  summary ""
  summary "Next: observe production, then rerun this workflow with phase \`decommission_retired\` and confirmation \`decommission-${retired_name}\`."
  log "Promoted ${NEW_DROPLET_NAME} to ${OLD_DROPLET_NAME}; retired old Droplet as ${retired_name}."
}

phase_rollback_stage() {
  local old_line old_id old_name old_status old_size new_count new_line new_id new_name new_status new_size

  old_line="$(require_one_droplet "$OLD_DROPLET_NAME")"
  read_droplet "$old_line" old_id old_name old_status old_size OLD_IP
  FIREWALL_ID="$(require_one_firewall "$FIREWALL_NAME")"
  open_runner_ssh "$FIREWALL_ID"
  add_known_host "$OLD_IP"

  new_count="$(droplet_count_by_name "$NEW_DROPLET_NAME")"
  if [ "$new_count" = "1" ]; then
    new_line="$(require_one_droplet "$NEW_DROPLET_NAME")"
    read_droplet "$new_line" new_id new_name new_status new_size NEW_IP
    add_known_host "$NEW_IP"
    ssh_host "$NEW_IP" "cd /opt/platform && docker compose -f ${COMPOSE_FILE} --env-file ${ENV_FILE} stop prefect-server prefect-worker airflow-webserver airflow-scheduler airflow-init raman || true" || true
  fi

  start_old_stack "$OLD_IP"
  summary "## Smaller Droplet stage rolled back"
  summary ""
  summary "- Restarted old stack on \`${OLD_DROPLET_NAME}\` at \`${OLD_IP}\`."
  summary "- If DNS was changed, point Squarespace A records back to \`${OLD_IP}\`."
  log "Rollback stage completed for ${OLD_DROPLET_NAME}."
}

phase_decommission_retired() {
  local canonical_line retired_line canonical_id canonical_name canonical_status canonical_size canonical_ip retired_id retired_name retired_status retired_size retired_ip

  canonical_line="$(require_one_droplet "$OLD_DROPLET_NAME")"
  retired_line="$(require_one_droplet "$RETIRED_DROPLET_NAME")"
  read_droplet "$canonical_line" canonical_id canonical_name canonical_status canonical_size canonical_ip
  read_droplet "$retired_line" retired_id retired_name retired_status retired_size retired_ip
  [ "$canonical_size" = "$TARGET_DROPLET_SIZE" ] || error "Canonical Droplet is ${canonical_size}, expected ${TARGET_DROPLET_SIZE}"

  check_public_smoke
  FIREWALL_ID="$(require_one_firewall "$FIREWALL_NAME")"
  doctl compute firewall remove-droplets "$FIREWALL_ID" --droplet-ids "$retired_id" || true
  doctl compute droplet delete "$retired_id" --force

  summary "## Retired Droplet decommissioned"
  summary ""
  summary "- Deleted retired Droplet: \`${RETIRED_DROPLET_NAME}\` at \`${retired_ip}\`"
  summary "- Production remains on \`${OLD_DROPLET_NAME}\` at \`${canonical_ip}\` with size \`${TARGET_DROPLET_SIZE}\`."
  log "Deleted retired Droplet ${RETIRED_DROPLET_NAME}."
}

main() {
  require_actions
  require_tool awk
  require_tool curl
  require_tool doctl
  require_tool jq
  require_tool rsync
  require_tool scp
  require_tool ssh
  validate_confirmation
  trap 'cleanup "$?"' EXIT

  case "$MIGRATION_PHASE" in
    stage) phase_stage ;;
    promote) phase_promote ;;
    rollback_stage) phase_rollback_stage ;;
    decommission_retired) phase_decommission_retired ;;
  esac
}

main "$@"
