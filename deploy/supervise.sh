#!/usr/bin/env bash
# Automatic app-process recovery for the household deployment
# (private-household-deployment ticket 06a).
#
#   deploy/supervise.sh start | stop | restart | status | run
#
# A lightweight watch loop around deploy/control.sh: while the WSL distribution
# is up, it keeps the app process alive, restarting it through control.sh if it
# exits. It supervises the APP PROCESS ONLY. It does not keep WSL itself alive
# (ticket 06b) and does not start anything after Windows boot (ticket 06c) — run
# it under whatever brings WSL up.
#
#   start   — start the app if it is not already up, then launch the watch loop
#             in the background (setsid, its own pidfile). Refuses if a
#             supervisor is already running; a repeated start never creates a
#             duplicate app.
#   stop    — stop the watch loop, then stop the app.
#   restart — stop then start.
#   status  — supervisor state + restart bookkeeping, then deploy/control.sh
#             status (its exit code is this command's exit code: 3 = app stopped).
#   run     — run the watch loop in the FOREGROUND (no detach, no pidfile churn);
#             for an external supervisor such as a systemd unit (ticket 06b) or a
#             test harness that owns the process lifetime. SIGTERM/SIGINT stops
#             the app and exits 0.
#
# Everything operates on the one explicit, absolute configuration resolved by
# lib.sh, so it behaves the same from any working directory.

set -euo pipefail
_SUPERVISE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib.sh
. "$_SUPERVISE_DIR/lib.sh"

CONTROL="$_SUPERVISE_DIR/control.sh"
SELF="$_SUPERVISE_DIR/supervise.sh"

_ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# One line to the supervisor log (always) and to stderr. When `start` spawns the
# loop it sends the loop's stdout/stderr to /dev/null, so the background case
# gets exactly one copy — in the file; `run` under systemd/journald or a
# terminal gets both.
_slog() {
  local line
  line="$(_ts) $*"
  printf '%s\n' "$line" >>"$DEPLOY_SUPERVISOR_LOGFILE" 2>/dev/null || true
  printf '%s\n' "$line" >&2
}

_write_state() {
  printf 'restarts=%s\nlast_restart=%s\n' "$1" "$2" \
    >"$DEPLOY_SUPERVISOR_STATEFILE" 2>/dev/null || true
}

_app_running() { deploy_pid_if_running >/dev/null 2>&1; }

# pid of the in-flight `control.sh` child, if the loop is mid-(re)start.
_loop_child=""

# Stop the app and exit. Runs from the TERM/INT trap so `supervise.sh stop` and
# a systemd unit stop both bring the whole deployment down — synchronously, with
# no orphaned control.sh child even if the signal lands mid-restart.
_loop_shutdown() {
  _slog "supervisor: signalled — stopping the app"
  if [ -n "$_loop_child" ] && kill -0 "$_loop_child" 2>/dev/null; then
    kill -TERM "$_loop_child" 2>/dev/null || true
    wait "$_loop_child" 2>/dev/null || true
  fi
  bash "$CONTROL" stop >>"$DEPLOY_SUPERVISOR_LOGFILE" 2>&1 || true
  rm -f "$DEPLOY_SUPERVISOR_PIDFILE"
  exit 0
}

# Run "$@" in the background and wait for it, so a TERM/INT during the call
# interrupts the `wait` at once (bash otherwise defers the trap until a
# foreground command returns) and the trap can kill the child. Echoes nothing;
# returns the child's exit status (non-zero only on the signal path, where the
# trap has already `exit`ed — callers append `|| true`).
_supervised_call() {
  local rc=0
  "$@" &
  _loop_child=$!
  wait "$_loop_child" || rc=$?
  _loop_child=""
  return "$rc"
}

# Double the caller's `backoff` (dynamic scope — only _watch_loop calls this),
# capped at RECIPE_DEPLOY_SUPERVISE_BACKOFF_MAX.
_bump_backoff() {
  backoff=$((backoff * 2))
  [ "$backoff" -gt "$RECIPE_DEPLOY_SUPERVISE_BACKOFF_MAX" ] \
    && backoff="$RECIPE_DEPLOY_SUPERVISE_BACKOFF_MAX"
  return 0
}

# The watch loop. It owns none of the app lifecycle itself — every start/stop
# goes through control.sh — so the supervised process stays exactly the one
# explicit-database uvicorn the rest of deploy/ manages.
#
# Crash-loop damping: a restart that fails, OR an app that comes back and then
# exits again within RECIPE_DEPLOY_SUPERVISE_BACKOFF_MAX seconds, grows a delay
# (doubling, capped at that value) that the loop waits out before the next
# restart. The delay resets once the app has held for that long. So a genuine
# one-off crash is restarted immediately, but a broken build cannot spin.
_watch_loop() {
  local restarts=0 backoff="$RECIPE_DEPLOY_SUPERVISE_INTERVAL" up_since=0 now
  trap _loop_shutdown TERM INT

  _slog "supervisor: watching (pid $$, poll ${RECIPE_DEPLOY_SUPERVISE_INTERVAL}s)"
  _write_state 0 -

  while true; do
    now="$(date +%s)"

    if _app_running; then
      if [ "$up_since" -ne 0 ] \
        && [ "$((now - up_since))" -ge "$RECIPE_DEPLOY_SUPERVISE_BACKOFF_MAX" ]; then
        backoff="$RECIPE_DEPLOY_SUPERVISE_INTERVAL"   # held long enough — stable
      fi
      _supervised_call sleep "$RECIPE_DEPLOY_SUPERVISE_INTERVAL" || true
      continue
    fi

    # App is down. If it had only just come back, it is crash-looping — wait out
    # the growing backoff before trying again.
    if [ "$up_since" -ne 0 ] \
      && [ "$((now - up_since))" -lt "$RECIPE_DEPLOY_SUPERVISE_BACKOFF_MAX" ]; then
      _slog "supervisor: app exited after $((now - up_since))s — backing off ${backoff}s"
      _supervised_call sleep "$backoff" || true
      _bump_backoff
    fi

    restarts=$((restarts + 1))
    _slog "supervisor: app is not running — restart attempt #$restarts"
    if [ -f "$DEPLOY_LOGFILE" ]; then
      tail -n 5 "$DEPLOY_LOGFILE" 2>/dev/null \
        | sed 's/^/  app| /' >>"$DEPLOY_SUPERVISOR_LOGFILE" 2>&1 || true
    fi

    if _supervised_call bash "$CONTROL" start >>"$DEPLOY_SUPERVISOR_LOGFILE" 2>&1; then
      up_since="$(date +%s)"
      _slog "supervisor: app restarted (#$restarts)"
      _write_state "$restarts" "$(_ts)"
    else
      up_since=0
      _slog "supervisor: restart #$restarts failed — see the app log above; will retry"
      _write_state "$restarts" "$(_ts) (failed)"
      _supervised_call sleep "$backoff" || true
      _bump_backoff
    fi
  done
}

# Take ownership of the supervisor pidfile and run the watch loop. The sole
# writer of the pidfile: `run` calls this directly, and the `__loop` that
# `start` spawns in the background calls it too, so there is never a second
# writer racing the loop's own EXIT cleanup.
_own_and_watch() {
  mkdir -p "$RECIPE_DEPLOY_RUNTIME_DIR"
  echo "$$" >"$DEPLOY_SUPERVISOR_PIDFILE"
  trap 'rm -f "$DEPLOY_SUPERVISOR_PIDFILE"' EXIT
  _watch_loop
}

_start() {
  if pid="$(deploy_supervisor_pid_if_running)"; then
    _deploy_die "already supervising (pid $pid) — use 'restart' or 'stop' first"
  fi
  if [ -f "$DEPLOY_SUPERVISOR_PIDFILE" ]; then
    echo "-- removing stale supervisor pidfile $DEPLOY_SUPERVISOR_PIDFILE"
    rm -f "$DEPLOY_SUPERVISOR_PIDFILE"
  fi
  mkdir -p "$RECIPE_DEPLOY_RUNTIME_DIR"

  # Bring the app up synchronously first, so a bad build or config fails the
  # operator's `start` right here instead of disappearing into the loop.
  if _app_running; then
    echo "-- app already running (pid $(deploy_pid_if_running)) — supervising it in place"
  else
    echo "-- starting the app"
    bash "$CONTROL" start
  fi

  echo "-- launching the supervisor"
  setsid bash "$SELF" __loop >/dev/null 2>&1 &

  # The loop writes its own pidfile as its first act — wait briefly for it.
  for _ in $(seq 1 20); do
    if pid="$(deploy_supervisor_pid_if_running)"; then
      echo "supervising (pid $pid); log: $DEPLOY_SUPERVISOR_LOGFILE"
      return 0
    fi
    sleep 0.25
  done
  _deploy_die "supervisor did not come up — see $DEPLOY_SUPERVISOR_LOGFILE"
}

_stop() {
  if pid="$(deploy_supervisor_pid_if_running)"; then
    echo "-- stopping the supervisor (pid $pid)"
    kill -TERM "$pid" 2>/dev/null || true
    # The supervisor's TERM handler stops the app before it exits, so give it
    # long enough for a control.sh stop (which itself waits on SIGTERM).
    for _ in $(seq 1 80); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.25
    done
    if kill -0 "$pid" 2>/dev/null; then
      echo "-- supervisor did not exit on SIGTERM, sending SIGKILL" >&2
      kill -KILL "$pid" 2>/dev/null || true
    fi
  else
    echo "-- no supervisor running"
  fi
  rm -f "$DEPLOY_SUPERVISOR_PIDFILE"

  # Always sweep the app: the supervisor's handler normally has it down
  # already, but a SIGKILLed supervisor (or a restart still in flight when it
  # was signalled) can leave the app or a fresh pidfile behind. control.sh stop
  # is a no-op when nothing is running.
  bash "$CONTROL" stop
}

_status() {
  if pid="$(deploy_supervisor_pid_if_running)"; then
    echo "supervisor       : running (pid $pid)"
  else
    echo "supervisor       : stopped"
  fi

  local restarts="0" last=""
  if [ -f "$DEPLOY_SUPERVISOR_STATEFILE" ]; then
    restarts="$(sed -n 's/^restarts=//p' "$DEPLOY_SUPERVISOR_STATEFILE" | tail -n 1)"
    last="$(sed -n 's/^last_restart=//p' "$DEPLOY_SUPERVISOR_STATEFILE" | tail -n 1)"
    [ -z "$restarts" ] && restarts="0"
  fi
  if [ -n "$last" ] && [ "$last" != "-" ]; then
    echo "app restarts     : $restarts (last: $last)"
  else
    echo "app restarts     : $restarts"
  fi

  if [ -f "$DEPLOY_SUPERVISOR_LOGFILE" ]; then
    echo "recent supervisor log ($DEPLOY_SUPERVISOR_LOGFILE):"
    tail -n 5 "$DEPLOY_SUPERVISOR_LOGFILE" | sed 's/^/  /'
  fi
  echo
  # control.sh status exits 3 when the app is stopped — let that be our code.
  bash "$CONTROL" status
}

_run_foreground() {
  if pid="$(deploy_supervisor_pid_if_running)"; then
    _deploy_die "already supervising (pid $pid)"
  fi
  if ! _app_running; then
    echo "-- starting the app"
    bash "$CONTROL" start
  fi
  _own_and_watch
}

case "${1:-}" in
  start) _start ;;
  stop) _stop ;;
  restart) _stop; _start ;;
  status) _status ;;
  run) _run_foreground ;;
  __loop) _own_and_watch ;;  # internal: the backgrounded watch loop `start` spawns
  -h | --help)
    echo "usage: deploy/supervise.sh {start|stop|restart|status|run}"
    echo "  Watch loop around deploy/control.sh — restarts the app process if it"
    echo "  exits while WSL stays up. Supervises the app process only (WSL"
    echo "  lifetime is 06b, start-on-boot is 06c)."
    exit 0 ;;
  *) echo "usage: deploy/supervise.sh {start|stop|restart|status|run}" >&2; exit 2 ;;
esac
