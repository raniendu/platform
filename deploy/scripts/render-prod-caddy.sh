#!/usr/bin/env bash
set -euo pipefail

flags_file="${1:-deploy/apps.prod.env}"
target_dir="${2:-deploy/caddy/prod-sites}"

if [ ! -f "$flags_file" ]; then
  echo "Production app flags file not found: ${flags_file}" >&2
  exit 1
fi

DEPLOY_DOTDEV=
DEPLOY_PREFECT=
DEPLOY_FLOW=
DEPLOY_PAPERCLIP=
DEPLOY_RAMAN=
DEPLOY_HOMI=
DEPLOY_VIKRAM=

# shellcheck disable=SC1090
. "$flags_file"

validate_bool() {
  local name="$1"
  local value="${!name:-}"
  case "$value" in
    true|false)
      ;;
    *)
      echo "${name} must be true or false in ${flags_file}; got '${value:-<unset>}'." >&2
      exit 1
      ;;
  esac
}

validate_bool DEPLOY_DOTDEV
validate_bool DEPLOY_PREFECT
validate_bool DEPLOY_FLOW
validate_bool DEPLOY_PAPERCLIP
validate_bool DEPLOY_RAMAN
validate_bool DEPLOY_HOMI
validate_bool DEPLOY_VIKRAM

mkdir -p "$target_dir"
find "$target_dir" -type f -name '*.caddy' -delete

if [ "$DEPLOY_DOTDEV" = true ]; then
  cat > "${target_dir}/10-dotdev.caddy" <<'EOF'
raniendu.dev {
	reverse_proxy dotdev:8501
}

http://www.raniendu.dev {
	redir https://raniendu.dev{uri} permanent
}

www.raniendu.dev {
	redir https://raniendu.dev{uri} permanent
}
EOF
else
  cat > "${target_dir}/10-dotdev.caddy" <<'EOF'
raniendu.dev {
	respond "DotDev is not deployed." 404
}

www.raniendu.dev {
	respond "DotDev is not deployed." 404
}
EOF
fi

if [ "$DEPLOY_PREFECT" = true ]; then
  cat > "${target_dir}/20-prefect.caddy" <<'EOF'
prefect.raniendu.dev {
	basic_auth {
		{$PREFECT_BASIC_AUTH_USER} {$PREFECT_BASIC_AUTH_HASH}
	}
	reverse_proxy prefect-server:4200
}
EOF
else
  cat > "${target_dir}/20-prefect.caddy" <<'EOF'
prefect.raniendu.dev {
	respond "Prefect is not deployed." 404
}
EOF
fi

if [ "$DEPLOY_FLOW" = true ]; then
  cat > "${target_dir}/30-flow.caddy" <<'EOF'
flow.raniendu.dev {
	reverse_proxy airflow-webserver:8080
}
EOF
else
  cat > "${target_dir}/30-flow.caddy" <<'EOF'
flow.raniendu.dev {
	respond "Flow is not deployed." 404
}
EOF
fi

if [ "$DEPLOY_PAPERCLIP" = true ]; then
  cat > "${target_dir}/40-paperclip.caddy" <<'EOF'
paperclip.raniendu.dev {
	basic_auth {
		{$PAPERCLIP_BASIC_AUTH_USER} {$PAPERCLIP_BASIC_AUTH_HASH}
	}
	reverse_proxy paperclip:3100
}
EOF
else
  cat > "${target_dir}/40-paperclip.caddy" <<'EOF'
paperclip.raniendu.dev {
	respond "Paperclip is not deployed." 404
}
EOF
fi

if [ "$DEPLOY_RAMAN" = true ]; then
  cat > "${target_dir}/50-raman.caddy" <<'EOF'
raman.raniendu.dev {
	reverse_proxy raman:8000
}
EOF
else
  cat > "${target_dir}/50-raman.caddy" <<'EOF'
raman.raniendu.dev {
	respond "Raman is not deployed." 404
}
EOF
fi

if [ "$DEPLOY_HOMI" = true ]; then
  cat > "${target_dir}/60-homi.caddy" <<'EOF'
homi.raniendu.dev {
	reverse_proxy homi:8000
}
EOF
else
  cat > "${target_dir}/60-homi.caddy" <<'EOF'
homi.raniendu.dev {
	respond "Homi is not deployed." 404
}
EOF
fi

if [ "$DEPLOY_VIKRAM" = true ]; then
  cat > "${target_dir}/70-vikram.caddy" <<'EOF'
vikram.raniendu.dev {
	reverse_proxy vikram:8000
}
EOF
else
  cat > "${target_dir}/70-vikram.caddy" <<'EOF'
vikram.raniendu.dev {
	respond "Vikram is not deployed." 404
}
EOF
fi
