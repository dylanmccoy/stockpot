#!/usr/bin/env bash
# Manual start / stop / status for the household deployment (private-household-
# deployment ticket 04a).
#
#   deploy/control.sh start | stop | restart | status | run
#
# No supervision, no auto-restart: automatic process recovery is ticket 06a,
# and keeping WSL / Windows alive is 06b / 06c. A single pidfile is the only
# duplicate guard here. Every subcommand operates on the explicit, absolute
# configuration resolved by lib.sh, so it behaves the same from any working
# directory.
#
#   start   — launch in the background (setsid, pidfile), wait for health
#   stop    — signal the background instance and wait for it to exit
#   restart — stop then start
#   status  — print the resolved config and whether it is running
#   run     — exec uvicorn in the FOREGROUND (no pidfile, no detach); for use
#             under an external supervisor or a test harness that owns the
#             process lifetime

set -euo pipefail
# shellcheck source=deploy/lib.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

_start() {
  if pid="$(deploy_pid_if_running)"; then
    _deploy_die "already running (pid $pid) — stop it first, or use 'restart'"
  fi
  [ -f "$DEPLOY_PIDFILE" ] && echo "-- removing stale pidfile $DEPLOY_PIDFILE"
  [ -f "$RECIPE_DEPLOY_FRONTEND_DIST/index.html" ] \
    || _deploy_die "no frontend build at $RECIPE_DEPLOY_FRONTEND_DIST — run deploy/install.sh"
  command -v "$RECIPE_DEPLOY_UV_BIN" >/dev/null 2>&1 \
    || _deploy_die "uv not found: $RECIPE_DEPLOY_UV_BIN"
  mkdir -p "$RECIPE_DEPLOY_RUNTIME_DIR" "$RECIPE_DEPLOY_DATA_DIR"

  echo "starting recipe deployment on 127.0.0.1:$RECIPE_DEPLOY_PORT"
  echo "  database : $RECIPE_DEPLOY_DB_FILE"
  echo "  logs     : $DEPLOY_LOGFILE"

  # setsid: the app runs in its own session/process group (leader pid == group
  # id), detached from this terminal — closing the shell does not SIGHUP it,
  # and `stop` can signal the whole group so no uv/uvicorn child is orphaned.
  setsid "$RECIPE_DEPLOY_UV_BIN" run uvicorn app.main:app \
    --host 127.0.0.1 --port "$RECIPE_DEPLOY_PORT" \
    >>"$DEPLOY_LOGFILE" 2>&1 &
  local pid=$!
  echo "$pid" >"$DEPLOY_PIDFILE"

  if deploy_wait_health "$RECIPE_DEPLOY_PORT" 30; then
    echo "started (pid $pid); GET /api/health is responding"
  else
    echo "deploy: server did not become healthy within 30s — last log lines:" >&2
    tail -n 20 "$DEPLOY_LOGFILE" >&2 || true
    kill -TERM "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    rm -f "$DEPLOY_PIDFILE"
    exit 1
  fi
}

_stop() {
  if pid="$(deploy_pid_if_running)"; then
    echo "stopping recipe deployment (pid $pid)"
    kill -TERM "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    for _ in $(seq 1 40); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.25
    done
    if kill -0 "$pid" 2>/dev/null; then
      echo "deploy: pid $pid did not exit on SIGTERM, sending SIGKILL" >&2
      kill -KILL "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
    fi
    rm -f "$DEPLOY_PIDFILE"
    echo "stopped"
  else
    rm -f "$DEPLOY_PIDFILE"
    echo "not running"
  fi
}

_run_foreground() {
  [ -f "$RECIPE_DEPLOY_FRONTEND_DIST/index.html" ] \
    || _deploy_die "no frontend build at $RECIPE_DEPLOY_FRONTEND_DIST — run deploy/install.sh"
  command -v "$RECIPE_DEPLOY_UV_BIN" >/dev/null 2>&1 \
    || _deploy_die "uv not found: $RECIPE_DEPLOY_UV_BIN"
  mkdir -p "$RECIPE_DEPLOY_DATA_DIR"
  echo "running recipe deployment in the foreground on 127.0.0.1:$RECIPE_DEPLOY_PORT (db: $RECIPE_DEPLOY_DB_FILE)"
  exec "$RECIPE_DEPLOY_UV_BIN" run uvicorn app.main:app \
    --host 127.0.0.1 --port "$RECIPE_DEPLOY_PORT"
}

_status() {
  deploy_print_config
  if [ -f "$RECIPE_DEPLOY_DB_FILE" ]; then
    echo "database file    : present ($(wc -c <"$RECIPE_DEPLOY_DB_FILE" | tr -d ' ') bytes)"
  else
    echo "database file    : MISSING (created on first start)"
  fi
  echo
  if pid="$(deploy_pid_if_running)"; then
    echo "state            : running (pid $pid)"
    if deploy_wait_health "$RECIPE_DEPLOY_PORT" 1; then
      echo "health           : GET /api/health OK"
    else
      echo "health           : NOT responding on 127.0.0.1:$RECIPE_DEPLOY_PORT (see $DEPLOY_LOGFILE)"
    fi
    return 0
  fi
  echo "state            : stopped"
  return 3
}

# uvicorn is launched from the backend package directory so `app.main:app`
# imports; the database location is passed explicitly and absolutely, never
# derived from the CWD.
cd "$RECIPE_DEPLOY_CHECKOUT/backend"
export RECIPE_DATABASE_URL="$DEPLOY_DATABASE_URL"
export RECIPE_FRONTEND_DIST="$RECIPE_DEPLOY_FRONTEND_DIST"

case "${1:-}" in
  start) _start ;;
  stop) _stop ;;
  restart) _stop; _start ;;
  status) _status ;;
  run) _run_foreground ;;
  *) echo "usage: deploy/control.sh {start|stop|restart|status|run}" >&2; exit 2 ;;
esac
