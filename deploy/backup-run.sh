#!/usr/bin/env bash
# Unattended daily SQLite snapshot for the household deployment (private-
# household-deployment ticket 07a).
#
#   deploy/backup-run.sh
#
# The one command a scheduler runs. On the target host that is Windows Task
# Scheduler, via `wsl.exe -d <distro> -- bash <checkout>/deploy/backup-run.sh`
# (deploy/windows/register-backup-task.ps1). Operator guide: README "Operating
# the server" runbook 12.
#
#   * Takes ONE live snapshot of RECIPE_DEPLOY_DB_FILE into
#     RECIPE_DEPLOY_BACKUP_DIR via scripts/backup.py (deploy_snapshot) —
#     SQLite's online backup facility, safe whether or not the app process is
#     running. It contacts no app, supervisor, or Tailscale, and needs no
#     terminal or app start-on-boot.
#   * Bounded: the snapshot runs under `timeout $RECIPE_DEPLOY_BACKUP_TIMEOUT`
#     (coreutils `timeout`), so a stuck database lock cannot wedge the task.
#     Task Scheduler's ExecutionTimeLimit is the on-host backstop.
#   * Success -> prints "-- backup ok: <path>", logs `ok <path>`, exits 0.
#   * ANY failure (missing database, unwritable destination, interrupted copy,
#     time limit) -> prints "deploy: backup failed: <reason>", logs
#     `FAIL <reason>`, exits non-zero, publishes no file, and leaves every
#     earlier snapshot untouched (scripts/backup.py never publishes a partial).
#
# One `<UTC ISO8601> ok|FAIL <detail>` line per run is appended to
# $DEPLOY_BACKUP_LOG. After a successful snapshot the job also applies local
# retention (ticket 07b) — keep the newest $RECIPE_DEPLOY_BACKUP_KEEP valid
# snapshots via `scripts/backup_status.py --prune`; a prune problem only warns,
# it never fails the backup. Freshness/age reporting is the same script without
# `--prune` (README "Operating the server" runbook 14).
#
# No `set -e`: the control flow inspects `timeout`'s exit code explicitly (a
# failed snapshot is logged and turned into a bounded non-zero exit, it does
# not abort the script mid-way).
set -uo pipefail
# shellcheck source=deploy/lib.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

# Internal re-entry: the main path runs this under `timeout` so a shell
# function (deploy_snapshot) can still be time-bounded. Prints only the
# snapshot path on stdout; backup.py's own "backup ok" line goes to stderr.
if [ "${1:-}" = "__snapshot" ]; then
  snap="$(deploy_snapshot "$RECIPE_DEPLOY_DB_FILE" "$RECIPE_DEPLOY_BACKUP_DIR")" || exit 1
  printf '%s\n' "$snap"
  exit 0
fi

_log() {
  # $1: ok|FAIL   $2: detail
  mkdir -p "$(dirname "$DEPLOY_BACKUP_LOG")" 2>/dev/null || true
  if ! printf '%s %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" >>"$DEPLOY_BACKUP_LOG" 2>/dev/null; then
    echo "deploy: could not append to the backup run log $DEPLOY_BACKUP_LOG" >&2
  fi
}

_prune_retention() {
  # Apply local retention once the snapshot is safely published (ticket 07b):
  # keep the newest RECIPE_DEPLOY_BACKUP_KEEP valid snapshots, drop older ones.
  # A prune problem never fails the backup job — the new snapshot already
  # succeeded — it only warns; `scripts/backup_status.py` reports the detail.
  ( cd "$RECIPE_DEPLOY_CHECKOUT/backend" \
    && "$RECIPE_DEPLOY_UV_BIN" run python scripts/backup_status.py \
         --dest-dir "$RECIPE_DEPLOY_BACKUP_DIR" \
         --log "$DEPLOY_BACKUP_LOG" \
         --keep "$RECIPE_DEPLOY_BACKUP_KEEP" \
         --max-age-hours "$RECIPE_DEPLOY_BACKUP_MAX_AGE_HOURS" \
         --prune --quiet >&2 ) \
    || echo "deploy: retention prune reported a problem — the snapshot is safe; run 'uv run python scripts/backup_status.py --dest-dir $RECIPE_DEPLOY_BACKUP_DIR' for detail" >&2
}

_finish_ok() {
  echo "-- backup ok: $1"
  _log ok "$1"
  _prune_retention
  exit 0
}

_finish_fail() {
  echo "deploy: backup failed: $1" >&2
  _log FAIL "$1"
  exit 1
}

echo "-- snapshotting $RECIPE_DEPLOY_DB_FILE -> $RECIPE_DEPLOY_BACKUP_DIR (app supervision not required)"

[ -f "$RECIPE_DEPLOY_DB_FILE" ] \
  || _finish_fail "deployment database $RECIPE_DEPLOY_DB_FILE does not exist — nothing to back up (start the deployment at least once)"

if command -v timeout >/dev/null 2>&1; then
  # -k 5: escalate to SIGKILL 5s after SIGTERM if the snapshot ignores it.
  out="$(timeout -k 5 "$RECIPE_DEPLOY_BACKUP_TIMEOUT" bash "$0" __snapshot)"
  rc=$?
else
  echo "deploy: WARNING coreutils 'timeout' not found — running the snapshot unbounded (Task Scheduler's ExecutionTimeLimit still applies on the host)" >&2
  out="$(bash "$0" __snapshot)"
  rc=$?
fi

if [ "$rc" -eq 0 ] && [ -n "$out" ] && [ -f "$out" ]; then
  _finish_ok "$out"
elif [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then
  # 124: timeout sent SIGTERM; 137 (128+9): it had to SIGKILL.
  _finish_fail "snapshot exceeded the ${RECIPE_DEPLOY_BACKUP_TIMEOUT}s time limit and was terminated — earlier snapshots left untouched"
else
  _finish_fail "snapshot did not complete (exit $rc) — earlier snapshots left untouched"
fi
