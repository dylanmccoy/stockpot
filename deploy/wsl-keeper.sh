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
# the supervisor if none is running (adopting an app the operator already
# started by hand), and re-launches it if it later disappears. Runbook 17
# supersedes runbook 16 — the keeper owns the whole lifecycle, so any keeper
# stop brings the supervisor and app down with it. So:
#
#   * closing the IDE and every development terminal changes nothing — the
#     keeper is owned by Task Scheduler, not by a shell;
#   * a controlled `wsl --shutdown` / `wsl --terminate` kills the keeper with
#     everything else; Task Scheduler restarts the `wsl.exe` invocation, WSL
#     boots, and `run` brings the supervisor and app back;
#   * a repeated task registration or a second `run` never doubles the keeper
#     (its own pidfile), the supervisor, or the app.
#
# Starting the keeper before an interactive Windows login (a full reboot) is the
# boot trigger ticket 06c adds to this same Scheduled Task (README runbook 18).
# With RECIPE_DEPLOY_KEEPER_SERVE set, `run` also re-asserts the private
# Tailscale ingress (deploy/tailscale-serve.sh apply, ticket 05a) once it is
# holding the app up, so the household's HTTPS origin returns after a reboot with
# nobody logged in.
#
#   run    — foreground; hold WSL up and keep the supervisor alive (and, with
#            RECIPE_DEPLOY_KEEPER_SERVE, the Tailscale ingress). SIGTERM /
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
TAILSCALE_SERVE="$_KEEPER_DIR/tailscale-serve.sh"

# A keeper "ok" heartbeat line is written to the keeper log about this often;
# every supervisor re-launch is always logged. Not a config knob — it only
# affects log verbosity, not behaviour.
KEEPER_OK_LOG_EVERY_S=300

# One line to the keeper log and to stderr, via lib.sh's shared logger. Task
# Scheduler discards the `wsl.exe` process output, so the file is the durable
# record; a terminal or `status` sees stderr too.
_klog() { _deploy_log "$DEPLOY_KEEPER_LOGFILE" "$@"; }

_supervisor_running() { deploy_supervisor_pid_if_running >/dev/null 2>&1; }

_keeper_shutting_down=0
_keeper_child=""

# Set once deploy/tailscale-serve.sh reports the ingress mapped, so the keeper
# stops re-checking it (the `--bg` Serve mapping is persistent — tailscaled
# owns it — and returns on its own after a Tailscale restart).
_ingress_asserted=0

# pid of the in-flight `sleep`, so a signal during the heartbeat wait interrupts
# it at once (bash defers a trap until the foreground command returns).
_keeper_sleep() {
  sleep "$1" &
  _keeper_child=$!
  wait "$_keeper_child" 2>/dev/null || true
  _keeper_child=""
}

# The keeper owns the whole deployment lifecycle: on any shutdown it stops the
# supervisor (which stops the app). Runbook 17 supersedes runbook 16 — do not
# run `deploy/supervise.sh` by hand as well.
_keeper_shutdown() {
  _keeper_shutting_down=1
  if [ -n "$_keeper_child" ] && kill -0 "$_keeper_child" 2>/dev/null; then
    kill -TERM "$_keeper_child" 2>/dev/null || true
  fi
  _klog "keeper: signalled — stopping the supervisor and the app"
  bash "$SUPERVISE" stop >>"$DEPLOY_KEEPER_LOGFILE" 2>&1 || true
  rm -f "$DEPLOY_KEEPER_PIDFILE"
  exit 0
}

# Bring a supervisor up if there is not one already (deploy/supervise.sh start
# adopts an app the operator started by hand per runbook 8, so this is
# idempotent). Never fails the caller: a supervisor that will not start (bad
# build, port in use) is logged and retried on the next heartbeat, so a
# transient fault at boot does not defeat the keeper.
_ensure_supervisor() {
  _supervisor_running && return 0
  _klog "keeper: no app supervisor running — starting deploy/supervise.sh"
  if bash "$SUPERVISE" start >>"$DEPLOY_KEEPER_LOGFILE" 2>&1; then
    _klog "keeper: supervisor started (pid $(deploy_supervisor_pid_if_running 2>/dev/null || echo '?'))"
  else
    _klog "keeper: supervisor start did not complete — see the log above; will retry"
  fi
}

# Opt-in: keep the private Tailscale ingress (ticket 05a) up unattended, so a
# reboot restores the household's HTTPS origin with nobody logged in.
_keeper_serve_enabled() {
  case "${RECIPE_DEPLOY_KEEPER_SERVE:-0}" in
    1 | true | yes | on | TRUE | YES | ON) return 0 ;;
    *) return 1 ;;
  esac
}

# Re-assert Tailscale Serve if it is not already pointing at this deployment's
# local origin. Best effort: a keeper that starts before the Windows Tailscale
# service is ready just logs and retries on the next heartbeat, and a host with
# no WSL-side Tailscale CLI (RECIPE_DEPLOY_KEEPER_SERVE left unset) never gets
# here. Never fails the caller. Sets _ingress_asserted once it is mapped.
_ensure_ingress() {
  _keeper_serve_enabled || return 0
  [ "$_ingress_asserted" = 1 ] && return 0
  if deploy_tailscale serve status 2>/dev/null \
    | grep -q "127.0.0.1:$RECIPE_DEPLOY_PORT"; then
    _ingress_asserted=1
    return 0
  fi
  _klog "keeper: private Tailscale ingress not mapped — running tailscale-serve.sh apply"
  if bash "$TAILSCALE_SERVE" apply >>"$DEPLOY_KEEPER_LOGFILE" 2>&1; then
    _ingress_asserted=1
    _klog "keeper: Tailscale ingress is up"
  else
    _klog "keeper: Tailscale ingress not up yet — see the log above; will retry"
  fi
}

_keeper_loop() {
  trap _keeper_shutdown TERM INT
  mkdir -p "$RECIPE_DEPLOY_RUNTIME_DIR"
  # noclobber so two racing `run` invocations cannot both believe they own the
  # pidfile (the _run guard catches the common case; Task Scheduler's
  # MultipleInstances=IgnoreNew the scheduled one). _run has already cleared a
  # stale file, so an existing file here means a live peer won the race.
  if ! (set -o noclobber; echo "$$" >"$DEPLOY_KEEPER_PIDFILE") 2>/dev/null; then
    if pid="$(deploy_keeper_pid_if_running)"; then
      _deploy_die "another keeper (pid $pid) won the startup race"
    fi
    rm -f "$DEPLOY_KEEPER_PIDFILE"
    echo "$$" >"$DEPLOY_KEEPER_PIDFILE"
  fi
  trap 'rm -f "$DEPLOY_KEEPER_PIDFILE"' EXIT

  # Tolerate a hand-edited non-numeric / zero heartbeat rather than dividing by
  # it or busy-looping on `sleep`.
  local hb="$RECIPE_DEPLOY_KEEPER_HEARTBEAT"
  case "$hb" in '' | *[!0-9]*) hb=30 ;; esac
  [ "$hb" -ge 1 ] || hb=1

  _klog "keeper: holding WSL up (pid $$, heartbeat ${hb}s)"
  _ensure_supervisor

  # `tailscale-serve.sh apply` refuses if the local origin is not answering, so
  # give the app a bounded moment to come up before the first attempt; a miss is
  # retried on every heartbeat until it is mapped.
  if _keeper_serve_enabled; then
    deploy_wait_health "$RECIPE_DEPLOY_PORT" 30 || true
    _ensure_ingress
  fi

  # Log an "ok" heartbeat roughly every KEEPER_OK_LOG_EVERY_S; always log a
  # re-launch.
  local ok_every healthy=""
  ok_every=$(( (KEEPER_OK_LOG_EVERY_S + hb - 1) / hb ))
  [ "$ok_every" -ge 1 ] || ok_every=1
  local ticks=0

  while true; do
    _keeper_sleep "$hb"
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
    # Cheap once mapped (a single early return); closes the boot race where the
    # keeper started before the Windows Tailscale service was ready.
    _ensure_ingress
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

  # Sweep: a SIGKILLed keeper (or one killed before its handler finished) can
  # leave the supervisor and app behind. Both stops are no-ops when nothing is
  # up. `stop` therefore always brings the whole deployment down.
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
    echo "  A Windows Scheduled Task runs 'run' via wsl.exe at boot and at logon"
    echo "  (deploy/windows/register-keeper-task.ps1; README runbooks 17-18)."
    echo "  Set RECIPE_DEPLOY_KEEPER_SERVE=1 to also re-assert the private"
    echo "  Tailscale ingress (deploy/tailscale-serve.sh apply) unattended."
    exit 0 ;;
  *) echo "usage: deploy/wsl-keeper.sh {run|stop|status}" >&2; exit 2 ;;
esac
