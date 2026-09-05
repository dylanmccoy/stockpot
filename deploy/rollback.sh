#!/usr/bin/env bash
# Return the household deployment to a previously retained, compatible
# application build (private-household-deployment ticket 04c).
#
#   deploy/rollback.sh [--list]
#   deploy/rollback.sh [--to <timestamp | build-dir>]
#
# This is the deliberate operator command to step back to an earlier build
# after an unsuitable update. It is NOT a data restore: the app restarts against
# the same explicit persistent database, household records are never touched,
# and a pre-maintenance snapshot is taken first. Recovering household DATA from
# a snapshot is a separate procedure (root README.md runbook 5 / the restore
# tickets).
#
# A schema-changing upgrade is a one-way door: once household data is on a newer
# schema an older build must not be run against it. Roll back a build only while
# the schema is unchanged (this deployment ships no schema change — root
# README.md runbook 10 / runbook 3).
#
# Retained builds come from deploy/update.sh, which copies the build it replaced
# into RECIPE_DEPLOY_BUILD_ARCHIVE (default: RECIPE_DEPLOY_DATA_DIR/builds) as
# <UTC timestamp>/, keeping the newest RECIPE_DEPLOY_BUILD_KEEP.
#
#   1. Resolve + validate the selected build (index.html + backend import smoke
#      against it) BEFORE stopping anything. A missing or unusable selection
#      aborts with the running deployment and its data completely intact.
#   2. Pre-maintenance snapshot of the deployment database.
#   3. Stop, swap the selected build in, and start against the same explicit
#      RECIPE_DATABASE_URL. If it fails to start, the build that was running is
#      put back and restarted.
#
# To move FORWARD to a newer build, build and deploy it with deploy/update.sh.

set -euo pipefail
# shellcheck source=deploy/lib.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

mode="rollback"
target=""
while [ $# -gt 0 ]; do
  case "$1" in
    --list) mode="list"; shift ;;
    --to) target="${2:?--to needs a timestamp or build directory}"; shift 2 ;;
    --to=*) target="${1#*=}"; shift ;;
    -h | --help)
      echo "usage: deploy/rollback.sh [--list] [--to <timestamp | build-dir>]"
      echo "  Switch the deployment back to a retained compatible build. With no"
      echo "  --to it uses the most recently retained build. Validates the build"
      echo "  and snapshots the database before switching; a bad selection leaves"
      echo "  the running deployment and its data intact. Never restores data."
      exit 0 ;;
    *) _deploy_die "unknown argument: $1" ;;
  esac
done

PREV="$RECIPE_DEPLOY_FRONTEND_DIST.prev"

if [ "$mode" = "list" ]; then
  echo "== retained builds in $RECIPE_DEPLOY_BUILD_ARCHIVE =="
  mapfile -t builds < <(deploy_retained_builds)
  if [ "${#builds[@]}" -eq 0 ]; then
    echo "(none — deploy/update.sh retains the build it replaces here)"
    exit 0
  fi
  for b in "${builds[@]}"; do
    if [ -f "$b/index.html" ]; then
      echo "  $(basename "$b")"
    else
      echo "  $(basename "$b")  (no index.html — unusable)"
    fi
  done
  exit 0
fi

echo "== recipe household deployment · rollback =="
deploy_print_config
echo

command -v "$RECIPE_DEPLOY_UV_BIN" >/dev/null 2>&1 \
  || _deploy_die "uv not found: $RECIPE_DEPLOY_UV_BIN"

# --- 1. resolve + validate the selected build (deployment untouched) ---
selected=""
if [ -n "$target" ]; then
  if [ -d "$target" ] && [ -f "$target/index.html" ]; then
    selected="$(_deploy_abs "$target")"
  elif [ -d "$target" ]; then
    _deploy_die "'$target' is not a usable build directory (no index.html); nothing switched, current deployment and data intact"
  elif [ -d "$RECIPE_DEPLOY_BUILD_ARCHIVE/$target" ]; then
    selected="$RECIPE_DEPLOY_BUILD_ARCHIVE/$target"
  else
    _deploy_die "no build '$target' — not a build directory and not a name in $RECIPE_DEPLOY_BUILD_ARCHIVE (try deploy/rollback.sh --list); nothing switched, current deployment and data intact"
  fi
else
  mapfile -t _builds < <(deploy_retained_builds)
  selected="${_builds[0]:-}"
  [ -n "$selected" ] \
    || _deploy_die "no retained build to roll back to in $RECIPE_DEPLOY_BUILD_ARCHIVE (deploy/update.sh retains the build it replaces); nothing switched, current deployment and data intact"
fi

echo "-- selected build: $selected"
echo "-- validating selected build (index.html + backend import smoke against it)"
deploy_validate_build "$selected" \
  || _deploy_die "selected build failed validation — nothing switched, current deployment and data intact"

# --- 2. pre-maintenance snapshot --------------------------------------
if [ -f "$RECIPE_DEPLOY_DB_FILE" ]; then
  echo "-- taking a pre-maintenance snapshot into $RECIPE_DEPLOY_BACKUP_DIR"
  snap_path="$(deploy_snapshot "$RECIPE_DEPLOY_DB_FILE" "$RECIPE_DEPLOY_BACKUP_DIR")" \
    || _deploy_die "pre-maintenance snapshot failed — deployment NOT switched, current build and data intact"
  echo "   snapshot: $snap_path"
else
  echo "-- no deployment database yet ($RECIPE_DEPLOY_DB_FILE) — nothing to snapshot"
fi

# --- 3. switch + restart against the explicit persistent database -----
# deploy_switch_build copies the selected build (it stays in the archive for a
# future rollback), stages it next to the live build, stops, swaps with two
# atomic renames, and starts. On a failed start it restores and restarts the
# build that was running (the database is never touched) and returns non-zero.
if deploy_switch_build "$selected"; then
  rm -rf "$PREV"
  echo
  echo "rollback complete. Serving $(basename "$selected") against $RECIPE_DEPLOY_DB_FILE."
  exit 0
fi

_deploy_die "rollback failed and was reverted to the previously running build; database untouched"
