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
