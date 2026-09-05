#!/usr/bin/env bash
# Repeatable install of the household deployment inside WSL (private-household-
# deployment ticket 04a).
#
#   deploy/install.sh [--adopt-from <sqlite-file>] [--skip-build]
#
# Idempotent: safe to re-run to pick up a new frontend build. It NEVER
# overwrites an existing deployment database — carrying the household's existing
# records in happens once, on the first install, via a live snapshot.
#
# Steps:
#   1. sanity-check the toolchain and the checkout
#   2. build the frontend (npm ci + npm run build) into the disposable dist/
#   3. create the persistent data / backup / runtime directories, outside the
#      checkout and outside dist/
#   4. adopt existing data: if the deployment database does not yet exist, take
#      a live snapshot of the source database (default: the dev checkout's
#      backend/recipe.db, override with --adopt-from) using scripts/backup.py
#      and copy it into place. If it already exists, leave it untouched.
#
# Start / stop / status are deploy/control.sh — this script starts nothing.

set -euo pipefail
# shellcheck source=deploy/lib.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

adopt_from=""
skip_build=0
while [ $# -gt 0 ]; do
  case "$1" in
    --adopt-from) adopt_from="${2:?--adopt-from needs a path}"; shift 2 ;;
    --adopt-from=*) adopt_from="${1#*=}"; shift ;;
    --skip-build) skip_build=1; shift ;;
    -h | --help) sed -n '2,26p' "$0"; exit 0 ;;
    *) _deploy_die "unknown argument: $1" ;;
  esac
done

echo "== recipe household deployment · install =="
deploy_print_config
echo

command -v "$RECIPE_DEPLOY_UV_BIN" >/dev/null 2>&1 \
  || _deploy_die "uv not found: $RECIPE_DEPLOY_UV_BIN"

# --- 2. frontend build --------------------------------------------------
if [ "$skip_build" -eq 1 ]; then
  echo "-- skipping frontend build (--skip-build)"
  [ -f "$RECIPE_DEPLOY_FRONTEND_DIST/index.html" ] \
    || _deploy_die "no build at $RECIPE_DEPLOY_FRONTEND_DIST and --skip-build was given"
else
  command -v "$RECIPE_DEPLOY_NPM_BIN" >/dev/null 2>&1 \
    || _deploy_die "npm not found: $RECIPE_DEPLOY_NPM_BIN"
  echo "-- building frontend into $RECIPE_DEPLOY_FRONTEND_DIST"
  (cd "$RECIPE_DEPLOY_CHECKOUT/frontend" && "$RECIPE_DEPLOY_NPM_BIN" ci && "$RECIPE_DEPLOY_NPM_BIN" run build)
fi
[ -f "$RECIPE_DEPLOY_FRONTEND_DIST/index.html" ] \
  || _deploy_die "frontend build produced no index.html at $RECIPE_DEPLOY_FRONTEND_DIST"

# --- 3. persistent directories, outside the checkout / disposable build ---
case "$RECIPE_DEPLOY_DB_FILE" in
  "$RECIPE_DEPLOY_CHECKOUT"/*)
    _deploy_die "database $RECIPE_DEPLOY_DB_FILE is inside the checkout — put it on persistent storage outside it" ;;
esac
case "$RECIPE_DEPLOY_DB_FILE" in
  "$RECIPE_DEPLOY_FRONTEND_DIST"/*)
    _deploy_die "database $RECIPE_DEPLOY_DB_FILE is inside the disposable frontend build" ;;
esac

echo "-- creating persistent directories"
mkdir -p "$RECIPE_DEPLOY_DATA_DIR" "$RECIPE_DEPLOY_BACKUP_DIR" "$RECIPE_DEPLOY_RUNTIME_DIR"
chmod 700 "$RECIPE_DEPLOY_DATA_DIR" "$RECIPE_DEPLOY_BACKUP_DIR" "$RECIPE_DEPLOY_RUNTIME_DIR" 2>/dev/null || true

# --- 4. adopt existing household data ---------------------------------
if [ -e "$RECIPE_DEPLOY_DB_FILE" ]; then
  echo "-- deployment database already present: $RECIPE_DEPLOY_DB_FILE"
  echo "   keeping it as-is (install never overwrites an existing deployment database)"
else
  src="$adopt_from"
  [ -n "$src" ] || src="$RECIPE_DEPLOY_CHECKOUT/backend/recipe.db"
  if [ -e "$src" ]; then
    echo "-- adopting existing household data from $src"
    echo "   taking a live snapshot into $RECIPE_DEPLOY_BACKUP_DIR first"
    snap_out="$(cd "$RECIPE_DEPLOY_CHECKOUT/backend" \
      && "$RECIPE_DEPLOY_UV_BIN" run python scripts/backup.py \
        --source "$src" --dest-dir "$RECIPE_DEPLOY_BACKUP_DIR")"
    echo "   $snap_out"
    snap_path="$(printf '%s\n' "$snap_out" | sed -n 's/^backup ok: //p' | tail -n 1)"
    if [ -z "$snap_path" ] || [ ! -f "$snap_path" ]; then
      _deploy_die "snapshot did not land where expected: $snap_out"
    fi
    tmp="$RECIPE_DEPLOY_DB_FILE.adopt.tmp"
    rm -f "$tmp"
    cp "$snap_path" "$tmp"
    chmod 600 "$tmp" 2>/dev/null || true
    mv "$tmp" "$RECIPE_DEPLOY_DB_FILE"
    echo "   adopted -> $RECIPE_DEPLOY_DB_FILE"
  else
    echo "-- no existing household database found (looked at $src)"
    echo "   a fresh empty database will be created at $RECIPE_DEPLOY_DB_FILE on first start"
  fi
fi

echo
echo "install complete. Start the deployment with:  deploy/control.sh start"
