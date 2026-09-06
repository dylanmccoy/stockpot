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

# UTC ISO-8601 timestamp (e.g. 2026-09-06T12:34:56Z) for log lines.
_deploy_ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# Append "<ts> <msg>" to logfile $1 (best effort — a log we cannot write is not
# fatal) and echo the same line to stderr. Shared by deploy/supervise.sh (06a)
# and deploy/wsl-keeper.sh (06b), which each keep their own activity log.
_deploy_log() {
  local logfile="$1"; shift
  local line
  line="$(_deploy_ts) $*"
  printf '%s\n' "$line" >>"$logfile" 2>/dev/null || true
  printf '%s\n' "$line" >&2
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

# Process supervision (private-household-deployment ticket 06a). deploy/supervise.sh
# runs a lightweight watch loop that restarts the app process if it exits while
# the WSL distribution stays up. It supervises the app process ONLY — keeping WSL
# alive is ticket 06b and starting after Windows boot is 06c.
#   RECIPE_DEPLOY_SUPERVISE_INTERVAL    — seconds between liveness checks (default 3)
#   RECIPE_DEPLOY_SUPERVISE_BACKOFF_MAX — cap, in seconds, on the delay the loop
#                                        inserts before a restart when the app is
#                                        crash-looping (a restart that failed, or
#                                        an app that stayed up less than one
#                                        interval). The delay doubles each time
#                                        and resets once the app holds. (default 60)
RECIPE_DEPLOY_SUPERVISE_INTERVAL="${RECIPE_DEPLOY_SUPERVISE_INTERVAL:-3}"
RECIPE_DEPLOY_SUPERVISE_BACKOFF_MAX="${RECIPE_DEPLOY_SUPERVISE_BACKOFF_MAX:-60}"

# WSL lifetime keeper (private-household-deployment ticket 06b). deploy/wsl-keeper.sh
# is the one long-lived foreground process a Windows Scheduled Task runs through
# `wsl.exe -d <distro> -- ...`: while it runs the WSL distribution stays up, and
# it holds exactly one deploy/supervise.sh (06a) above the app. Keeping WSL alive
# is NOT something a WSL systemd service can do (the distro stops when its last
# process exits); starting it before an interactive Windows login is ticket 06c.
#   RECIPE_DEPLOY_KEEPER_HEARTBEAT — seconds between keeper liveness checks of the
#                                   supervisor (it re-launches a supervisor that
#                                   has gone). Default 30.
RECIPE_DEPLOY_KEEPER_HEARTBEAT="${RECIPE_DEPLOY_KEEPER_HEARTBEAT:-30}"

# Private HTTPS ingress (private-household-deployment ticket 05a). Tailscale
# Serve runs on the *Windows* host and proxies its localhost:$RECIPE_DEPLOY_PORT
# — which WSL2 forwards to this app — out onto the tailnet over HTTPS, private
# to permitted household devices. deploy/tailscale-serve.sh and
# deploy/net-check.sh source this file for these values.
#
#   RECIPE_DEPLOY_TAILSCALE_BIN — the Tailscale CLI. From inside WSL this is
#     `tailscale.exe` (the Windows client owns the tailnet node and the
#     localhost proxy); on the Windows side it is `tailscale`. An absolute
#     path works too. Default: tailscale.exe (the documented WSL topology).
#   RECIPE_DEPLOY_HTTPS_PORT — the tailnet port Serve listens on. 443 is the
#     only port a browser reaches without an explicit ":port", so it is the
#     default. App listeners stay on 127.0.0.1 regardless.
RECIPE_DEPLOY_TAILSCALE_BIN="${RECIPE_DEPLOY_TAILSCALE_BIN:-tailscale.exe}"
RECIPE_DEPLOY_HTTPS_PORT="${RECIPE_DEPLOY_HTTPS_PORT:-443}"

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

# Wall-clock ceiling (seconds) for one unattended backup job (private-household-
# deployment ticket 07a). deploy/backup-run.sh runs the snapshot under `timeout`
# so a stuck database lock cannot leave the scheduled task running forever; the
# job then reports failure and the prior snapshots are left in place.
RECIPE_DEPLOY_BACKUP_TIMEOUT="${RECIPE_DEPLOY_BACKUP_TIMEOUT:-300}"

# Local backup retention + freshness target (private-household-deployment ticket
# 07b). After a successful snapshot deploy/backup-run.sh keeps the newest
# RECIPE_DEPLOY_BACKUP_KEEP valid snapshots and drops older ones;
# `scripts/backup_status.py` reports the latest success, its age, and the latest
# failure, flagging no success or a success older than
# RECIPE_DEPLOY_BACKUP_MAX_AGE_HOURS. Retention is count-based on purpose: a
# failed run publishes no snapshot, so it can never evict an earlier success.
RECIPE_DEPLOY_BACKUP_KEEP="${RECIPE_DEPLOY_BACKUP_KEEP:-14}"
RECIPE_DEPLOY_BACKUP_MAX_AGE_HOURS="${RECIPE_DEPLOY_BACKUP_MAX_AGE_HOURS:-24}"

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
# Append-only diagnostics for the unattended backup job (ticket 07a): one line
# per run, `<UTC ISO8601> ok <snapshot>` / `<UTC ISO8601> FAIL <reason>`. Kept
# with the operational logs, distinct from the snapshot files themselves so a
# data problem reads apart from a serving one (spec item 37). Freshness and
# retention reporting on top of this is ticket 07b.
# shellcheck disable=SC2034  # used by deploy/backup-run.sh, which sources this file
DEPLOY_BACKUP_LOG="$RECIPE_DEPLOY_RUNTIME_DIR/backup-runs.log"

# deploy/supervise.sh (private-household-deployment ticket 06a): the watch loop's
# own pidfile — distinct from DEPLOY_PIDFILE above so the supervisor and the app
# never share a file — plus an activity log and a small state file it rewrites
# with the running restart count and last-restart timestamp.
# shellcheck disable=SC2034  # used by supervise.sh, which sources this file
DEPLOY_SUPERVISOR_PIDFILE="$RECIPE_DEPLOY_RUNTIME_DIR/recipe-supervisor.pid"
# shellcheck disable=SC2034
DEPLOY_SUPERVISOR_LOGFILE="$RECIPE_DEPLOY_RUNTIME_DIR/recipe-supervisor.log"
# shellcheck disable=SC2034
DEPLOY_SUPERVISOR_STATEFILE="$RECIPE_DEPLOY_RUNTIME_DIR/recipe-supervisor.state"

# deploy/wsl-keeper.sh (private-household-deployment ticket 06b): the keeper's
# own pidfile (distinct from the app's and the supervisor's, so all three are
# independent) and an activity log — one heartbeat line while the supervisor is
# healthy, plus a line whenever the keeper has to re-launch it.
# shellcheck disable=SC2034  # used by wsl-keeper.sh, which sources this file
DEPLOY_KEEPER_PIDFILE="$RECIPE_DEPLOY_RUNTIME_DIR/recipe-keeper.pid"
# shellcheck disable=SC2034
DEPLOY_KEEPER_LOGFILE="$RECIPE_DEPLOY_RUNTIME_DIR/recipe-keeper.log"

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
tailscale cli    : $RECIPE_DEPLOY_TAILSCALE_BIN
tailnet https    : :$RECIPE_DEPLOY_HTTPS_PORT -> http://127.0.0.1:$RECIPE_DEPLOY_PORT
frontend build   : $RECIPE_DEPLOY_FRONTEND_DIST
database (abs)   : $RECIPE_DEPLOY_DB_FILE
database url     : $DEPLOY_DATABASE_URL
backup directory : $RECIPE_DEPLOY_BACKUP_DIR
backup run log   : $DEPLOY_BACKUP_LOG
backup job limit : ${RECIPE_DEPLOY_BACKUP_TIMEOUT}s
backup retention : keep newest $RECIPE_DEPLOY_BACKUP_KEEP valid snapshots
backup freshness : flag no success / success older than ${RECIPE_DEPLOY_BACKUP_MAX_AGE_HOURS}h
runtime directory: $RECIPE_DEPLOY_RUNTIME_DIR
build archive    : $RECIPE_DEPLOY_BUILD_ARCHIVE (keep $RECIPE_DEPLOY_BUILD_KEEP)
EOF
}

# Echo the live pid recorded in pidfile $1 and return 0, or return 1 if it is
# absent / malformed / dead. A stale pidfile whose pid has been recycled by an
# unrelated process is rejected when /proc/<pid>/cmdline is readable and does
# not contain the marker $2 (the command the process should be running).
_deploy_pid_from_file() {
  local pidfile="$1" marker="$2" pid
  [ -f "$pidfile" ] || return 1
  pid="$(cat "$pidfile" 2>/dev/null || true)"
  case "$pid" in
    '' | *[!0-9]*) return 1 ;;
  esac
  kill -0 "$pid" 2>/dev/null || return 1
  if [ -r "/proc/$pid/cmdline" ] \
    && ! tr '\0' ' ' <"/proc/$pid/cmdline" | grep -q "$marker"; then
    return 1
  fi
  printf '%s\n' "$pid"
  return 0
}

# Echoes the live app leader pid and returns 0, or returns 1 if not running.
# Not a full anti-duplication guard (that is ticket 06a's supervisor) — but a
# recycled stale pidfile is rejected (see _deploy_pid_from_file).
deploy_pid_if_running() { _deploy_pid_from_file "$DEPLOY_PIDFILE" "uvicorn"; }

# Echoes the live supervisor-loop pid and returns 0, or returns 1 if no
# supervisor is running.
deploy_supervisor_pid_if_running() {
  _deploy_pid_from_file "$DEPLOY_SUPERVISOR_PIDFILE" "supervise.sh"
}

# Echoes the live WSL-lifetime keeper pid and returns 0, or returns 1 if no
# keeper is running. A stale pidfile left by an abrupt `wsl --shutdown` names a
# dead (or recycled) pid and is rejected, so the next launch starts clean.
deploy_keeper_pid_if_running() {
  _deploy_pid_from_file "$DEPLOY_KEEPER_PIDFILE" "wsl-keeper.sh"
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

# Copy the built frontend at $1 into the retention area as <UTC timestamp>[-NN]/,
# prune to the newest RECIPE_DEPLOY_BUILD_KEEP, and echo the archived path.
# update.sh calls this with the build it just replaced, so deploy/rollback.sh
# can return to it. The -NN suffix (zero-padded, lexically after the bare stamp
# and before the next second) disambiguates a same-second collision without
# breaking the chronological sort deploy_retained_builds relies on.
deploy_archive_build() {
  local src="$1" stamp dest tmp all i
  [ -f "$src/index.html" ] || { echo "deploy: nothing to archive at $src" >&2; return 1; }
  mkdir -p "$RECIPE_DEPLOY_BUILD_ARCHIVE" || return 1
  stamp="$RECIPE_DEPLOY_BUILD_ARCHIVE/$(date -u +%Y%m%dT%H%M%SZ)"
  dest="$stamp"
  i=1
  while [ -e "$dest" ]; do
    dest="$stamp-$(printf '%02d' "$i")"
    i=$((i + 1))
  done
  tmp="$dest.tmp"
  rm -rf "$tmp"
  cp -a "$src" "$tmp" || { rm -rf "$tmp"; return 1; }
  mv "$tmp" "$dest" || { rm -rf "$tmp"; return 1; }
  # Prune oldest first. deploy_retained_builds is newest-first, so everything
  # from index RECIPE_DEPLOY_BUILD_KEEP onward is surplus.
  mapfile -t all < <(deploy_retained_builds)
  for (( i = RECIPE_DEPLOY_BUILD_KEEP; i < ${#all[@]}; i++ )); do
    rm -rf "${all[i]}"
  done
  printf '%s\n' "$dest"
}

# Switch the served frontend build to the one at $1 and (re)start the deployment
# against the one explicit database.
#
# If $1 is already <dist>.staging (update.sh built it there for an atomic swap)
# it is used in place; otherwise it is copied there first, leaving $1 untouched
# (rollback.sh's source is a retained archive build it must keep). Only two
# atomic renames then switch it in, so a failure while materialising it (bad
# copy, or $1 IS the live dir) leaves the running deployment untouched. On a
# failed start the build that was running is put back and restarted, and this
# returns non-zero. On success the build it replaced is left at <dist>.prev for
# the caller to archive or drop.
deploy_switch_build() {
  local src="$1"
  local prev="$RECIPE_DEPLOY_FRONTEND_DIST.prev"
  local staged="$RECIPE_DEPLOY_FRONTEND_DIST.staging"

  if [ "$src" != "$staged" ]; then
    rm -rf "$staged"
    cp -a "$src" "$staged" \
      || { rm -rf "$staged"; echo "deploy: could not stage the new build from $src" >&2; return 1; }
  fi
  [ -f "$staged/index.html" ] \
    || { rm -rf "$staged"; echo "deploy: staged build has no index.html — nothing switched" >&2; return 1; }

  if deploy_pid_if_running >/dev/null; then
    echo "-- stopping the running deployment"
    bash "$_DEPLOY_DIR/control.sh" stop
  fi
  echo "-- switching the served build"
  rm -rf "$prev"
  [ -e "$RECIPE_DEPLOY_FRONTEND_DIST" ] && mv "$RECIPE_DEPLOY_FRONTEND_DIST" "$prev"
  mv "$staged" "$RECIPE_DEPLOY_FRONTEND_DIST"

  echo "-- starting the deployment"
  bash "$_DEPLOY_DIR/control.sh" start && return 0

  echo "deploy: the new build did not start — restoring the build that was running" >&2
  rm -rf "$RECIPE_DEPLOY_FRONTEND_DIST"
  if [ -e "$prev" ]; then
    mv "$prev" "$RECIPE_DEPLOY_FRONTEND_DIST"
    bash "$_DEPLOY_DIR/control.sh" start || true
  fi
  return 1
}

# --- private HTTPS ingress helpers (ticket 05a) ----------------------------
# Shared by deploy/tailscale-serve.sh and deploy/net-check.sh. The Tailscale
# CLI is invoked exactly as configured; nothing here needs tailnet credentials,
# so a stub on PATH makes the whole path testable in CI.

# The one local origin Serve proxies: the deployment's loopback listener.
# Every other site derives host:port from this rather than re-inlining it.
deploy_serve_target() {
  printf 'http://127.0.0.1:%s\n' "$RECIPE_DEPLOY_PORT"
}

# Run the configured Tailscale CLI. Returns its exit status; output passes
# through untouched. `command -v` first so a missing CLI is one clear message
# rather than a bare shell "not found".
deploy_tailscale() {
  command -v "$RECIPE_DEPLOY_TAILSCALE_BIN" >/dev/null 2>&1 \
    || { echo "deploy: Tailscale CLI not found: $RECIPE_DEPLOY_TAILSCALE_BIN (set RECIPE_DEPLOY_TAILSCALE_BIN)" >&2; return 127; }
  "$RECIPE_DEPLOY_TAILSCALE_BIN" "$@"
}

# Echo the Funnel state as one word, always exit 0:
#   on      — `tailscale funnel status` reports an active public mapping
#   off     — it ran and reported no funnel
#   unknown — the query could not run (CLI missing, errored, or too old)
# Funnel is never part of this deployment. `apply` refuses on "on"; net-check
# treats "unknown" as a failure too — a safety check that cannot confirm its
# invariant must not pass.
deploy_funnel_state() {
  local out
  if ! out="$(deploy_tailscale funnel status 2>/dev/null)"; then
    echo unknown
    return 0
  fi
  if printf '%s\n' "$out" | grep -Eqi '(Funnel on|https://[^ ]+ \(Funnel\)|:[0-9]+ *\(Funnel\))'; then
    echo on
  else
    echo off
  fi
}

# Echo the tailnet HTTPS base URL for this node (https://<magicdns-name>/),
# from `tailscale status --json` .Self.DNSName. Parsed with the configured
# Python (as deploy_http_ok's fallback does) rather than a text scrape: the
# JSON carries a DNSName for .Self and every .Peer, so a grep + `head -1`
# would depend on Go's field order. Returns non-zero if the CLI or the field
# is unavailable.
deploy_tailnet_url() {
  local name py
  py='import sys, json; d = json.load(sys.stdin); print((d.get("Self") or {}).get("DNSName", "").rstrip("."))'
  name="$(deploy_tailscale status --json 2>/dev/null | "$RECIPE_DEPLOY_UV_BIN" run python -c "$py" 2>/dev/null)" || return 1
  [ -n "$name" ] || return 1
  printf 'https://%s/\n' "$name"
}
