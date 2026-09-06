#!/usr/bin/env bash
# WSL-lifetime keeper for the household deployment
# (private-household-deployment ticket 06b).
#
#   deploy/wsl-keeper.sh run | stop | status
#
# The one long-lived foreground process a Windows Scheduled Task launches with
#
#   wsl.exe -d <distro> -- bash <checkout>/deploy/wsl-keeper.sh run
#
# While `run` is alive the WSL distribution stays up (a distro stops when its
# last process exits — a systemd service inside WSL cannot hold it open). `run`
# keeps exactly one deploy/supervise.sh (ticket 06a) above the app: it starts
# the supervisor if none is running, adopts one that already is, and re-launches
# it if it later disappears. So:
#
#   * closing the IDE and every development terminal changes nothing — the
#     keeper is owned by Task Scheduler, not by a shell;
#   * a controlled `wsl --shutdown` / `wsl --terminate` kills the keeper with
#     everything else; Task Scheduler restarts the `wsl.exe` invocation, WSL
#     boots, and `run` brings the supervisor and app back;
#   * a repeated task registration or a second `run` never doubles the keeper
#     (its own pidfile), the supervisor, or the app.
#
# Starting the keeper before an interactive Windows login (full reboot) and
# running Tailscale ingress unattended are ticket 06c — this slice provides the
# WSL lifetime arrangement 06c builds the boot trigger onto.
#
#   run    — foreground; hold WSL up and keep the supervisor alive. SIGTERM /
#            SIGINT (Task Scheduler "End task", or `wsl-keeper.sh stop`) stops
#            the supervisor and the app and exits 0.
#   stop   — signal a running `run` so it brings the deployment down, then sweep.
#   status — keeper state + recent keeper log, then deploy/supervise.sh status
#            (its exit code is this command's exit code: 3 = app stopped).
#
# Everything operates on the one explicit, absolute configuration resolved by
# lib.sh, so it behaves the same from any working directory.

set -euo pipefail
_KEEPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib.sh
. "$_KEEPER_DIR/lib.sh"

SUPERVISE="$_KEEPER_DIR/supervise.sh"

_ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# One line to the keeper log (always) and to stderr. Task Scheduler discards the
# `wsl.exe` process output, so the file is the durable record; a terminal or
# `status` sees stderr too.
_klog() {
  local line
  line="$(_ts) $*"
  printf '%s\n' "$line" >>"$DEPLOY_KEEPER_LOGFILE" 2>/dev/null || true
  printf '%s\n' "$line" >&2
}

_supervisor_running() { deploy_supervisor_pid_if_running >/dev/null 2>&1; }

# Did this keeper start the supervisor (1), or adopt one already running (0)?
# Only a supervisor the keeper started is torn down on shutdown — an adopted one
# belongs to the operator (deploy/supervise.sh start, runbook 16).
_keeper_owns_supervisor=0
_keeper_shutting_down=0
_keeper_child=""

# pid of the in-flight `sleep`, so a signal during the heartbeat wait interrupts
# it at once (bash defers a trap until the foreground command returns).
_keeper_sleep() {
  sleep "$1" &
  _keeper_child=$!
  wait "$_keeper_child" 2>/dev/null || true
  _keeper_child=""
}

_keeper_shutdown() {
  _keeper_shutting_down=1
  if [ -n "$_keeper_child" ] && kill -0 "$_keeper_child" 2>/dev/null; then
    kill -TERM "$_keeper_child" 2>/dev/null || true
  fi
  if [ "$_keeper_owns_supervisor" = 1 ] && _supervisor_running; then
    _klog "keeper: signalled — stopping the supervisor and the app"
    bash "$SUPERVISE" stop >>"$DEPLOY_KEEPER_LOGFILE" 2>&1 || true
  else
    _klog "keeper: signalled — leaving the operator-started supervisor in place"
  fi
  rm -f "$DEPLOY_KEEPER_PIDFILE"
  exit 0
}

# Bring a supervisor up if there is not one already. Sets _keeper_owns_supervisor.
# Never fails the caller: a supervisor that will not start (bad build, port in
# use) is logged and retried on the next heartbeat, so a transient fault at boot
# does not defeat the keeper.
_ensure_supervisor() {
  if _supervisor_running; then
    [ "$_keeper_owns_supervisor" = 1 ] \
      || _klog "keeper: a supervisor is already running (pid $(deploy_supervisor_pid_if_running)) — adopting it"
    return 0
  fi
  _klog "keeper: no app supervisor running — starting deploy/supervise.sh"
  if bash "$SUPERVISE" start >>"$DEPLOY_KEEPER_LOGFILE" 2>&1; then
    _keeper_owns_supervisor=1
    _klog "keeper: supervisor started (pid $(deploy_supervisor_pid_if_running 2>/dev/null || echo '?'))"
  else
    _klog "keeper: supervisor start did not complete — see the log above; will retry"
  fi
}

_keeper_loop() {
  trap _keeper_shutdown TERM INT
  mkdir -p "$RECIPE_DEPLOY_RUNTIME_DIR"
  echo "$$" >"$DEPLOY_KEEPER_PIDFILE"
  trap 'rm -f "$DEPLOY_KEEPER_PIDFILE"' EXIT

  _klog "keeper: holding WSL up (pid $$, heartbeat ${RECIPE_DEPLOY_KEEPER_HEARTBEAT}s)"
  _ensure_supervisor

  # Log an "ok" heartbeat about every 5 minutes; always log a re-launch.
  local ok_every healthy=""
  ok_every=$(( (300 + RECIPE_DEPLOY_KEEPER_HEARTBEAT - 1) / RECIPE_DEPLOY_KEEPER_HEARTBEAT ))
  [ "$ok_every" -ge 1 ] || ok_every=1
  local ticks=0

  while true; do
    _keeper_sleep "$RECIPE_DEPLOY_KEEPER_HEARTBEAT"
    [ "$_keeper_shutting_down" = 1 ] && break

    if _supervisor_running; then
      if [ "$healthy" != 1 ] || [ "$((ticks % ok_every))" -eq 0 ]; then
        _klog "keeper: ok — supervisor $(deploy_supervisor_pid_if_running), $(deploy_pid_if_running >/dev/null 2>&1 && echo 'app up' || echo 'app down')"
      fi
      healthy=1
    else
      healthy=0
      _klog "keeper: app supervisor has gone — re-launching it"
      _ensure_supervisor
    fi
    ticks=$((ticks + 1))
  done
}

_run() {
  if pid="$(deploy_keeper_pid_if_running)"; then
    _deploy_die "already keeping WSL up (pid $pid) — use 'stop' first"
  fi
  if [ -f "$DEPLOY_KEEPER_PIDFILE" ]; then
    echo "-- removing stale keeper pidfile $DEPLOY_KEEPER_PIDFILE"
    rm -f "$DEPLOY_KEEPER_PIDFILE"
  fi
  _keeper_loop
}

_stop() {
  if pid="$(deploy_keeper_pid_if_running)"; then
    echo "-- stopping the keeper (pid $pid)"
    kill -TERM "$pid" 2>/dev/null || true
    # The keeper's handler stops the supervisor (which stops the app, itself a
    # SIGTERM wait) before it exits — allow for both.
    for _ in $(seq 1 120); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.25
    done
    if kill -0 "$pid" 2>/dev/null; then
      echo "-- keeper did not exit on SIGTERM, sending SIGKILL" >&2
      kill -KILL "$pid" 2>/dev/null || true
    fi
  else
    echo "-- no keeper running"
  fi
  rm -f "$DEPLOY_KEEPER_PIDFILE"

  # Sweep: a SIGKILLed keeper (or one that had adopted the supervisor) can leave
  # the supervisor and app behind. Both stops are no-ops when nothing is up.
  bash "$SUPERVISE" stop
}

_status() {
  if pid="$(deploy_keeper_pid_if_running)"; then
    echo "keeper           : running (pid $pid)"
  else
    echo "keeper           : stopped"
  fi
  if [ -f "$DEPLOY_KEEPER_LOGFILE" ]; then
    echo "recent keeper log ($DEPLOY_KEEPER_LOGFILE):"
    tail -n 5 "$DEPLOY_KEEPER_LOGFILE" | sed 's/^/  /'
  fi
  echo
  # supervise.sh status ends with control.sh status — exit 3 when the app is
  # stopped. Let that be our exit code.
  bash "$SUPERVISE" status
}

case "${1:-}" in
  run) _run ;;
  stop) _stop ;;
  status) _status ;;
  -h | --help)
    echo "usage: deploy/wsl-keeper.sh {run|stop|status}"
    echo "  Long-lived foreground process that holds the WSL distribution up and"
    echo "  keeps one deploy/supervise.sh (and so the app) running above it."
    echo "  A Windows Scheduled Task runs 'run' via wsl.exe (ticket 06b); the"
    echo "  boot-before-login trigger and unattended Tailscale are ticket 06c."
    exit 0 ;;
  *) echo "usage: deploy/wsl-keeper.sh {run|stop|status}" >&2; exit 2 ;;
esac
