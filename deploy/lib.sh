# shellcheck shell=bash
# Sourced by deploy/install.sh and deploy/control.sh — not run on its own.
#
# Resolves the household deployment configuration (private-household-deployment
# ticket 04a) into one set of absolute paths that every control operates on, so
# `start` / `stop` / `status` behave identically no matter which directory the
# operator runs them from (spec item 27: a different working directory must
# never silently create a second household database).
#
# Every value has an explicit source — deploy/deploy.env (git-ignored, copied
# from deploy.env.example) or the environment — and a sensible default. The
# environment is also how the test harness and the later Windows-side wiring
# (tickets 06b/06c) inject values.

_deploy_die() {
  echo "deploy: $*" >&2
  exit 2
}

_DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_DEPLOY_DEFAULT_CHECKOUT="$(cd "$_DEPLOY_DIR/.." && pwd)"

# --- operator config file -------------------------------------------------
DEPLOY_ENV_FILE="${RECIPE_DEPLOY_ENV_FILE:-$_DEPLOY_DIR/deploy.env}"
if [ -f "$DEPLOY_ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$DEPLOY_ENV_FILE"
  set +a
fi

# --- inputs: explicit value first, then a default -----------------------
RECIPE_DEPLOY_WSL_DISTRO="${RECIPE_DEPLOY_WSL_DISTRO:-${WSL_DISTRO_NAME:-unknown}}"
RECIPE_DEPLOY_CHECKOUT="${RECIPE_DEPLOY_CHECKOUT:-$_DEPLOY_DEFAULT_CHECKOUT}"
RECIPE_DEPLOY_UV_BIN="${RECIPE_DEPLOY_UV_BIN:-uv}"
RECIPE_DEPLOY_NPM_BIN="${RECIPE_DEPLOY_NPM_BIN:-npm}"
RECIPE_DEPLOY_PORT="${RECIPE_DEPLOY_PORT:-8000}"

[ -d "$RECIPE_DEPLOY_CHECKOUT/backend" ] \
  || _deploy_die "RECIPE_DEPLOY_CHECKOUT=$RECIPE_DEPLOY_CHECKOUT is not a recipe checkout (no backend/)"
RECIPE_DEPLOY_CHECKOUT="$(cd "$RECIPE_DEPLOY_CHECKOUT" && pwd)"

RECIPE_DEPLOY_DATA_DIR="${RECIPE_DEPLOY_DATA_DIR:-$HOME/.local/share/recipe-app}"
RECIPE_DEPLOY_DB_FILE="${RECIPE_DEPLOY_DB_FILE:-$RECIPE_DEPLOY_DATA_DIR/recipe.db}"
RECIPE_DEPLOY_BACKUP_DIR="${RECIPE_DEPLOY_BACKUP_DIR:-$RECIPE_DEPLOY_DATA_DIR/backups}"
RECIPE_DEPLOY_RUNTIME_DIR="${RECIPE_DEPLOY_RUNTIME_DIR:-$RECIPE_DEPLOY_DATA_DIR/run}"
RECIPE_DEPLOY_FRONTEND_DIST="${RECIPE_DEPLOY_FRONTEND_DIST:-$RECIPE_DEPLOY_CHECKOUT/frontend/dist}"

# Retained previous builds for deploy/rollback.sh (private-household-deployment
# ticket 04c). deploy/update.sh copies the build it replaces into here as
# <UTC timestamp>/; rollback.sh switches the deployment back to one of them.
# Kept outside the checkout and the disposable live build by default.
RECIPE_DEPLOY_BUILD_ARCHIVE="${RECIPE_DEPLOY_BUILD_ARCHIVE:-$RECIPE_DEPLOY_DATA_DIR/builds}"
RECIPE_DEPLOY_BUILD_KEEP="${RECIPE_DEPLOY_BUILD_KEEP:-5}"

# Absolutise the paths so they never resolve against the caller's CWD.
_deploy_abs() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s\n' "$(pwd)/$1" ;;
  esac
}
RECIPE_DEPLOY_DATA_DIR="$(_deploy_abs "$RECIPE_DEPLOY_DATA_DIR")"
RECIPE_DEPLOY_DB_FILE="$(_deploy_abs "$RECIPE_DEPLOY_DB_FILE")"
RECIPE_DEPLOY_BACKUP_DIR="$(_deploy_abs "$RECIPE_DEPLOY_BACKUP_DIR")"
RECIPE_DEPLOY_RUNTIME_DIR="$(_deploy_abs "$RECIPE_DEPLOY_RUNTIME_DIR")"
RECIPE_DEPLOY_FRONTEND_DIST="$(_deploy_abs "$RECIPE_DEPLOY_FRONTEND_DIST")"
RECIPE_DEPLOY_BUILD_ARCHIVE="$(_deploy_abs "$RECIPE_DEPLOY_BUILD_ARCHIVE")"

DEPLOY_PIDFILE="$RECIPE_DEPLOY_RUNTIME_DIR/recipe.pid"
# shellcheck disable=SC2034  # used by control.sh, which sources this file
DEPLOY_LOGFILE="$RECIPE_DEPLOY_RUNTIME_DIR/recipe.log"

# sqlite:/// + an absolute path is four slashes. This is the single explicit
# database location every start uses.
DEPLOY_DATABASE_URL="sqlite:///$RECIPE_DEPLOY_DB_FILE"

# The database must live on persistent storage, never inside the checkout or the
# disposable frontend build. Enforced here — in the resolver every entrypoint
# sources — not just in install.sh, so a hand-edited deploy.env cannot slip a
# checkout-local database past `control.sh start`.
case "$RECIPE_DEPLOY_DB_FILE" in
  "$RECIPE_DEPLOY_CHECKOUT"/* | "$RECIPE_DEPLOY_FRONTEND_DIST"/*)
    _deploy_die "database $RECIPE_DEPLOY_DB_FILE is inside the checkout or the disposable frontend build — put it on persistent storage outside both" ;;
esac

deploy_print_config() {
  cat <<EOF
WSL distribution : $RECIPE_DEPLOY_WSL_DISTRO
checkout         : $RECIPE_DEPLOY_CHECKOUT
uv executable    : $RECIPE_DEPLOY_UV_BIN
npm executable   : $RECIPE_DEPLOY_NPM_BIN
loopback address : 127.0.0.1:$RECIPE_DEPLOY_PORT
frontend build   : $RECIPE_DEPLOY_FRONTEND_DIST
database (abs)   : $RECIPE_DEPLOY_DB_FILE
database url     : $DEPLOY_DATABASE_URL
backup directory : $RECIPE_DEPLOY_BACKUP_DIR
runtime directory: $RECIPE_DEPLOY_RUNTIME_DIR
build archive    : $RECIPE_DEPLOY_BUILD_ARCHIVE (keep $RECIPE_DEPLOY_BUILD_KEEP)
EOF
}

# Echoes the live leader pid and returns 0, or returns 1 if not running.
# Not a full anti-duplication guard (that is ticket 06a) — but a stale pidfile
# whose pid has been recycled by an unrelated process is rejected when
# /proc/<pid>/cmdline is readable and doesn't look like our uvicorn.
deploy_pid_if_running() {
  [ -f "$DEPLOY_PIDFILE" ] || return 1
  local pid
  pid="$(cat "$DEPLOY_PIDFILE" 2>/dev/null || true)"
  case "$pid" in
    '' | *[!0-9]*) return 1 ;;
  esac
  kill -0 "$pid" 2>/dev/null || return 1
  if [ -r "/proc/$pid/cmdline" ] \
    && ! tr '\0' ' ' <"/proc/$pid/cmdline" | grep -q "uvicorn"; then
    return 1
  fi
  printf '%s\n' "$pid"
  return 0
}

# HTTP liveness probe: prefer curl, fall back to the configured Python so the
# check never adds an unguarded curl dependency to whatever sources this file
# (including `backend/tests/test_deploy.py` under `uv run pytest`).
deploy_http_ok() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -fsS -m 2 "$url" >/dev/null 2>&1
  else
    "$RECIPE_DEPLOY_UV_BIN" run python -c \
      'import sys,urllib.request; urllib.request.urlopen(sys.argv[1], timeout=2)' \
      "$url" >/dev/null 2>&1
  fi
}

deploy_wait_health() {
  local port="$1" timeout="${2:-30}" deadline
  deadline=$(($(date +%s) + timeout))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    if deploy_http_ok "http://127.0.0.1:$port/api/health"; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

# Take a live snapshot of $1 into directory $2 via scripts/backup.py and echo
# the resulting snapshot path. backup.py writes recipe-<UTC timestamp>.db; the
# timestamp format sorts chronologically, so the newest snapshot is the last
# one lexically — pick it from the directory rather than parsing stdout.
# Shared by install.sh (data adoption) and update.sh (pre-maintenance backup).
deploy_snapshot() {
  local source="$1" dest_dir="$2" snap
  mkdir -p "$dest_dir"
  # backup.py's own "backup ok: ..." line goes to stderr so this function's
  # stdout is only the snapshot path (callers capture it with $(...)).
  ( cd "$RECIPE_DEPLOY_CHECKOUT/backend" \
    && "$RECIPE_DEPLOY_UV_BIN" run python scripts/backup.py \
      --source "$source" --dest-dir "$dest_dir" >&2 ) \
    || return 1
  snap="$(printf '%s\n' "$dest_dir"/recipe-*.db | sort | tail -n 1)"
  [ -f "$snap" ] || return 1
  printf '%s\n' "$snap"
}

# Validate a built-frontend directory: it must contain index.html and the
# backend must import cleanly with RECIPE_FRONTEND_DIST pointed at it (app.main
# builds the app at import and raises if the dist has no index.html). Prints why
# and returns non-zero on failure, with no side effects — callers keep the
# running deployment and its data intact when this fails. Shared by update.sh
# (staged build) and rollback.sh (selected previous build).
deploy_validate_build() {
  local dist="$1"
  [ -f "$dist/index.html" ] \
    || { echo "deploy: build has no index.html: $dist" >&2; return 1; }
  ( cd "$RECIPE_DEPLOY_CHECKOUT/backend" \
    && RECIPE_DATABASE_URL="$DEPLOY_DATABASE_URL" \
       RECIPE_FRONTEND_DIST="$dist" \
       "$RECIPE_DEPLOY_UV_BIN" run python -c "import app.main" >&2 ) \
    || { echo "deploy: backend import smoke failed against $dist" >&2; return 1; }
}

# Newest-first list of retained build directories under RECIPE_DEPLOY_BUILD_ARCHIVE.
deploy_retained_builds() {
  [ -d "$RECIPE_DEPLOY_BUILD_ARCHIVE" ] || return 0
  find "$RECIPE_DEPLOY_BUILD_ARCHIVE" -mindepth 1 -maxdepth 1 -type d | sort -r
}

# Copy the built frontend at $1 into the retention area as <UTC timestamp>/,
# prune to the newest RECIPE_DEPLOY_BUILD_KEEP, and echo the archived path.
# Used by update.sh (retain the build being replaced) and rollback.sh (retain
# the build being switched away from, so a roll-forward is still possible).
deploy_archive_build() {
  local src="$1" stamp dest tmp all drop i
  [ -f "$src/index.html" ] || { echo "deploy: nothing to archive at $src" >&2; return 1; }
  mkdir -p "$RECIPE_DEPLOY_BUILD_ARCHIVE" || return 1
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  dest="$RECIPE_DEPLOY_BUILD_ARCHIVE/$stamp"
  # An update immediately followed by a rollback can land in the same second.
  [ -e "$dest" ] && dest="$dest-$$"
  tmp="$dest.tmp"
  rm -rf "$tmp"
  cp -a "$src" "$tmp" || { rm -rf "$tmp"; return 1; }
  mv "$tmp" "$dest" || { rm -rf "$tmp"; return 1; }
  mapfile -t all < <(find "$RECIPE_DEPLOY_BUILD_ARCHIVE" -mindepth 1 -maxdepth 1 -type d | sort)
  drop=$(( ${#all[@]} - RECIPE_DEPLOY_BUILD_KEEP ))
  for (( i = 0; i < drop; i++ )); do
    rm -rf "${all[i]}"
  done
  printf '%s\n' "$dest"
}
