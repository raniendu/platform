#!/usr/bin/env bash
set -euo pipefail

command="${1:-}"
flags_file="${2:-deploy/apps.prod.env}"

usage() {
  cat >&2 <<'EOF'
Usage: deploy/scripts/prod-app-flags.sh <command> [flags-file]

Commands:
  validate        Validate production deploy flags.
  github-outputs Print GitHub Actions output key/value pairs.
EOF
}

if [ -z "$command" ]; then
  usage
  exit 2
fi

normalize_bool() {
  local name="$1"
  local value="${!name:-}"

  case "$value" in
    true|false)
      ;;
    True|TRUE)
      value=true
      ;;
    False|FALSE)
      value=false
      ;;
    *)
      echo "${name} must be true or false in ${flags_file}; got '${value:-<unset>}'." >&2
      exit 1
      ;;
  esac

  printf -v "$name" '%s' "$value"
}

join_by() {
  local delimiter="$1"
  shift || true
  local IFS="$delimiter"
  printf '%s' "$*"
}

load_flags() {
  if [ ! -f "$flags_file" ]; then
    echo "Production app flags file not found: ${flags_file}" >&2
    exit 1
  fi

  DEPLOY_DOTDEV=
  DEPLOY_PREFECT=
  DEPLOY_FLOW=
  DEPLOY_PAPERCLIP=
  DEPLOY_RAMAN=

  # shellcheck disable=SC1090
  . "$flags_file"

  normalize_bool DEPLOY_DOTDEV
  normalize_bool DEPLOY_PREFECT
  normalize_bool DEPLOY_FLOW
  normalize_bool DEPLOY_PAPERCLIP
  normalize_bool DEPLOY_RAMAN
}

build_lists() {
  profiles=()
  enabled_pull_services=(postgres caddy)
  disabled_services=()
  disabled_containers=()

  if [ "$DEPLOY_DOTDEV" = true ]; then
    profiles+=(dotdev)
    enabled_pull_services+=(dotdev)
  else
    disabled_services+=(dotdev)
    disabled_containers+=(platform-dotdev)
  fi

  if [ "$DEPLOY_PREFECT" = true ]; then
    profiles+=(prefect)
    enabled_pull_services+=(prefect-server prefect-worker)
  else
    disabled_services+=(prefect-server prefect-worker)
    disabled_containers+=(platform-prefect-server platform-prefect-worker)
  fi

  if [ "$DEPLOY_FLOW" = true ]; then
    profiles+=(flow)
    enabled_pull_services+=(airflow-init airflow-webserver airflow-scheduler)
  else
    disabled_services+=(airflow-init airflow-webserver airflow-scheduler)
    disabled_containers+=(platform-airflow-init platform-airflow-webserver platform-airflow-scheduler)
  fi

  if [ "$DEPLOY_PAPERCLIP" = true ]; then
    profiles+=(paperclip)
    enabled_pull_services+=(paperclip-db-init paperclip)
  else
    disabled_services+=(paperclip-db-init paperclip)
    disabled_containers+=(platform-paperclip-db-init platform-paperclip)
  fi

  if [ "$DEPLOY_RAMAN" = true ]; then
    profiles+=(raman)
    enabled_pull_services+=(raman)
  else
    disabled_services+=(raman)
    disabled_containers+=(platform-raman)
  fi
}

load_flags
build_lists

case "$command" in
  validate)
    exit 0
    ;;
  github-outputs)
    {
      printf 'deploy_dotdev=%s\n' "$DEPLOY_DOTDEV"
      printf 'deploy_prefect=%s\n' "$DEPLOY_PREFECT"
      printf 'deploy_flow=%s\n' "$DEPLOY_FLOW"
      printf 'deploy_paperclip=%s\n' "$DEPLOY_PAPERCLIP"
      printf 'deploy_raman=%s\n' "$DEPLOY_RAMAN"
      printf 'compose_profiles=%s\n' "$(join_by , "${profiles[@]}")"
      printf 'enabled_pull_services=%s\n' "$(join_by ' ' "${enabled_pull_services[@]}")"
      printf 'disabled_services=%s\n' "$(join_by ' ' "${disabled_services[@]}")"
      printf 'disabled_containers=%s\n' "$(join_by ' ' "${disabled_containers[@]}")"
    }
    ;;
  *)
    usage
    exit 2
    ;;
esac
