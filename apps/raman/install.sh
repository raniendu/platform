#!/usr/bin/env bash
# install.sh — install raman on a new machine.
#
# Two paths, auto-detected:
#   1. Run inside an existing platform checkout (e.g. apps/raman/install.sh):
#      installs from that checkout, no clone.
#   2. Run anywhere else (or piped from curl): clones raniendu/platform to
#      $RAMAN_INSTALL_DIR (default ~/.local/share/raman) via `gh repo clone`,
#      then installs from there.
#
# In both cases the package is installed as an isolated `uv tool`, which
# exposes `raman` and `raman-api` on PATH.

set -euo pipefail

REPO="raniendu/platform"
INSTALL_DIR="${RAMAN_INSTALL_DIR:-$HOME/.local/share/raman}"
PYTHON_VERSION="${RAMAN_PYTHON_VERSION:-3.13}"

bold() { printf '\n\033[1m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
warn() { printf '\033[33mwarn:\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; }

# 1. Locate or fetch the source tree ----------------------------------------

source_dir=""
script_path="${BASH_SOURCE[0]:-}"
if [ -n "$script_path" ] && [ -f "$script_path" ]; then
  candidate="$(cd "$(dirname "$script_path")" && pwd)"
  while [ "$candidate" != "/" ]; do
    if [ -f "$candidate/apps/raman/pyproject.toml" ]; then
      source_dir="$candidate"
      break
    fi
    candidate="$(dirname "$candidate")"
  done
fi

if [ -z "$source_dir" ]; then
  bold "Fetching $REPO into $INSTALL_DIR"
  if ! command -v gh >/dev/null 2>&1; then
    err "gh (GitHub CLI) is required to clone the private repo."
    err "Install from https://cli.github.com/ and rerun."
    exit 1
  fi
  if ! gh auth status >/dev/null 2>&1; then
    err "gh is not authenticated. Run: gh auth login"
    exit 1
  fi
  mkdir -p "$(dirname "$INSTALL_DIR")"
  if [ -d "$INSTALL_DIR/.git" ]; then
    if [ -n "$(git -C "$INSTALL_DIR" status --porcelain)" ]; then
      warn "$INSTALL_DIR has uncommitted changes; skipping pull."
    else
      info "Updating existing checkout"
      git -C "$INSTALL_DIR" pull --ff-only
    fi
  else
    gh repo clone "$REPO" "$INSTALL_DIR"
  fi
  source_dir="$INSTALL_DIR"
else
  bold "Using existing checkout at $source_dir"
fi

raman_dir="$source_dir/apps/raman"
spec_root="$raman_dir/spec"

if [ ! -f "$raman_dir/pyproject.toml" ]; then
  err "Expected $raman_dir/pyproject.toml; aborting."
  exit 1
fi

# 2. Ensure uv is installed -------------------------------------------------

if ! command -v uv >/dev/null 2>&1; then
  bold "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# 3. Install raman as an isolated uv tool -----------------------------------

bold "Installing raman (Python $PYTHON_VERSION) from $raman_dir"
uv tool install \
  --force \
  --python "$PYTHON_VERSION" \
  --from "$raman_dir" \
  raman

# 4. Record install metadata for `raman update` -----------------------------

meta_dir="${XDG_CONFIG_HOME:-$HOME/.config}/raman"
meta_file="$meta_dir/install.toml"
mkdir -p "$meta_dir"

git_sha=""
if [ -d "$source_dir/.git" ]; then
  git_sha="$(git -C "$source_dir" rev-parse HEAD 2>/dev/null || true)"
fi
installed_at="$(date -u +"%Y-%m-%dT%H:%M:%S+00:00")"

{
  printf '# Written by raman install/update — do not edit by hand.\n'
  printf 'source_dir = "%s"\n' "$source_dir"
  printf 'installed_at = "%s"\n' "$installed_at"
  printf 'python_version = "%s"\n' "$PYTHON_VERSION"
  if [ -n "$git_sha" ]; then
    printf 'git_sha = "%s"\n' "$git_sha"
  fi
} > "$meta_file"

# 5. Post-install summary ---------------------------------------------------

if bin_dir="$(uv tool dir --bin 2>/dev/null)"; then
  :
else
  bin_dir="$HOME/.local/bin"
fi

bold "Installed."
info "Binaries:    $bin_dir/raman, $bin_dir/raman-api"
info "Spec root:   $spec_root"
info "Source tree: $source_dir"
info "Metadata:    $meta_file"

case ":$PATH:" in
  *":$bin_dir:"*) ;;
  *)
    bold "Add $bin_dir to PATH:"
    printf '  export PATH="%s:$PATH"\n' "$bin_dir"
    ;;
esac

state_dir="${RAMAN_STATE_DIR:-$HOME/.raman}"

bold "Required env (add to ~/.zshrc or ~/.bashrc):"
cat <<EOF
  export RAMAN_SPEC_ROOT="$spec_root"
  export RAMAN_DB_PATH="$state_dir/raman.sqlite3"
  export RAMAN_GROCERY_LIST_PATH="$state_dir/grocery_lists.json"
  export DBOS_SYSTEM_DATABASE_URL="sqlite:///$state_dir/dbos.sqlite3"
EOF

bold "Model provider (pick one):"
cat <<EOF
  # Local Ollama (default):
  export OLLAMA_BASE_URL="http://localhost:11434/v1"
  export RAMAN_DEV_MODEL="gemma4:26b"

  # Or DigitalOcean serverless inference:
  # export RAMAN_MODEL_PROVIDER=digitalocean
  # export DO_INFERENCE_API_KEY=...
  # export RAMAN_DEV_MODEL="gemma-4-31B-it"
EOF

bold "Optional (see $raman_dir/.env.example for the full list):"
info "PARALLEL_API_KEY, TELEGRAM_BOT_TOKEN, GOBIND_TELEGRAM_*, LEO_TELEGRAM_*, ..."

bold "Smoke test:"
info "raman --version"
info "raman --once --prompt 'say pong'"

bold "Updating later:"
info "raman update           # fast-forward + reinstall from $source_dir"
info "raman update --check   # show what would change"
