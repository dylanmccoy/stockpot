#!/usr/bin/env bash
# Deploy a schema-preserving application update (private-household-deployment
# ticket 04b).
#
#   deploy/update.sh [--staging-dir <prebuilt-dist>] [-h]
#
# Repeatable update procedure. It prepares and validates the new build BEFORE it
# touches the running deployment, takes a pre-maintenance snapshot, then switches
# and restarts against the one explicit persistent database:
#
#   1. Prepare the new build in a staging directory next to the live one
#      (`<frontend-dist>.staging`) and validate it — the frontend build output
#      and a backend import smoke against the staged assets. A failure here
#      leaves the current deployment and its data completely untouched.
#   2. Snapshot the deployment database with scripts/backup.py (the
#      pre-maintenance recovery point). A snapshot failure also aborts before
#      the switch.
#   3. Stop the deployment, swap the staged build in, and start it again with
#      deploy/control.sh — which always passes the configured absolute
#      RECIPE_DATABASE_URL. If the new build fails to start, roll the served
#      build back to the previous one so the household is never left down.
#
# On a successful update the build it replaced is copied into the build archive
# (RECIPE_DEPLOY_BUILD_ARCHIVE) so deploy/rollback.sh can return to it on demand
# (ticket 04c) — that is a deliberate operator command, distinct from the
# in-run rollback below that only guards a failed switch.
#
# This procedure never resets the database and never runs a schema-changing
# upgrade. A future schema change needs a reviewed, data-preserving migration
# before it can be installed (see root README.md runbook 3).

set -euo pipefail
# shellcheck source=deploy/lib.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

staging_from=""
while [ $# -gt 0 ]; do
  case "$1" in
    --staging-dir) staging_from="${2:?--staging-dir needs a path}"; shift 2 ;;
    --staging-dir=*) staging_from="${1#*=}"; shift ;;
    -h | --help)
      echo "usage: deploy/update.sh [--staging-dir <prebuilt-dist>]"
      echo "  Prepares and validates a new build, snapshots the database, then"
      echo "  switches the running deployment to it. A failed preparation leaves"
      echo "  the current deployment and data intact. Never resets the database."
      exit 0 ;;
    *) _deploy_die "unknown argument: $1" ;;
  esac
done

STAGING="$RECIPE_DEPLOY_FRONTEND_DIST.staging"
PREV="$RECIPE_DEPLOY_FRONTEND_DIST.prev"

echo "== recipe household deployment · update =="
deploy_print_config
echo

command -v "$RECIPE_DEPLOY_UV_BIN" >/dev/null 2>&1 \
  || _deploy_die "uv not found: $RECIPE_DEPLOY_UV_BIN"

# --- 1. prepare + validate the new build (running deployment untouched) ---
if [ -n "$staging_from" ]; then
  staging_from="$(_deploy_abs "$staging_from")"
  [ -f "$staging_from/index.html" ] \
    || _deploy_die "--staging-dir $staging_from has no index.html — nothing prepared, current deployment left intact"
  echo "-- using prebuilt staging dir: $staging_from"
  rm -rf "$STAGING"
  cp -a "$staging_from" "$STAGING"
else
  command -v "$RECIPE_DEPLOY_NPM_BIN" >/dev/null 2>&1 \
    || _deploy_die "npm not found: $RECIPE_DEPLOY_NPM_BIN"
  echo "-- building new frontend into staging: $STAGING"
  rm -rf "$STAGING"
  if ! ( cd "$RECIPE_DEPLOY_CHECKOUT/frontend" \
      && "$RECIPE_DEPLOY_NPM_BIN" ci \
      && "$RECIPE_DEPLOY_NPM_BIN" run build -- --outDir "$STAGING" --emptyOutDir ); then
    rm -rf "$STAGING"
    _deploy_die "frontend build failed — current deployment and data left intact"
  fi
  echo "-- syncing backend dependencies"
  if ! ( cd "$RECIPE_DEPLOY_CHECKOUT/backend" && "$RECIPE_DEPLOY_UV_BIN" sync ); then
    rm -rf "$STAGING"
    _deploy_die "backend dependency sync failed — current deployment and data left intact"
  fi
fi

echo "-- validating staged build (index.html + backend import smoke against the staged assets)"
deploy_validate_build "$STAGING" \
  || { rm -rf "$STAGING"; _deploy_die "staged build failed validation — current deployment and data left intact"; }

# --- 2. pre-maintenance snapshot ----------------------------------------
if [ -f "$RECIPE_DEPLOY_DB_FILE" ]; then
  echo "-- taking a pre-maintenance snapshot into $RECIPE_DEPLOY_BACKUP_DIR"
  snap_path="$(deploy_snapshot "$RECIPE_DEPLOY_DB_FILE" "$RECIPE_DEPLOY_BACKUP_DIR")" \
    || { rm -rf "$STAGING"; _deploy_die "pre-maintenance snapshot failed — deployment NOT switched, current build and data intact"; }
  echo "   snapshot: $snap_path"
else
  echo "-- no deployment database yet ($RECIPE_DEPLOY_DB_FILE) — nothing to snapshot"
fi

# --- 3. switch + restart against the explicit persistent database -------
# deploy_switch_build stages the new build, stops, swaps it in with two atomic
# renames, and starts. On a failed start it restores and restarts the build
# that was running (the ticket's "leave the current usable deployment intact"
# guarantee applied to a failed switch — distinct from ticket 04c's deliberate
# return to an older build) and returns non-zero.
if deploy_switch_build "$STAGING"; then
  # Retain the build we just replaced so deploy/rollback.sh (ticket 04c) can
  # return to it on demand. A failure here does not fail the update — the new
  # build is already serving.
  if [ -d "$PREV" ]; then
    if archived="$(deploy_archive_build "$PREV")"; then
      echo "-- retained the previous build for rollback: $archived"
    else
      echo "deploy: warning: could not archive the previous build (rollback would need deploy/rollback.sh --to <dir>)" >&2
    fi
  fi
  rm -rf "$PREV"
  echo
  echo "update complete. Serving the new build against $RECIPE_DEPLOY_DB_FILE."
  exit 0
fi

_deploy_die "update failed and was rolled back to the previous build; database untouched"
