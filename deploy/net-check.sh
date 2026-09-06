#!/usr/bin/env bash
# Connectivity diagnostics for the private HTTPS ingress (private-household-
# deployment ticket 05a).
#
#   deploy/net-check.sh [--local-only]
#
# Repeatable check that the deployment is reachable the intended way and only
# the intended way. Run it after first setup, and again after a Tailscale /
# WSL / Windows restart to confirm recovery. Every check prints PASS / FAIL
# with a one-line reason; the script exits non-zero if any check fails OR
# cannot confirm its invariant (a safety check that cannot verify itself does
# not pass).
#
# Checks:
#   1. the app answers on 127.0.0.1:$RECIPE_DEPLOY_PORT (GET /api/health)
#   2. NOTHING is listening on that port on a non-loopback address — no LAN or
#      public listener bypassing the Tailscale ingress
#   3. Tailscale is up and the backend is Running        (skipped: --local-only)
#   4. Serve maps the tailnet HTTPS port to the local origin   ( "" )
#   5. Funnel is OFF — no public exposure                      ( "" )
#   6. the tailnet HTTPS URL resolves for this node            ( "" )
#
# --local-only runs 1-2 only: useful from inside WSL, where the Windows
# Tailscale CLI may not be on PATH. The Tailscale checks need no tailnet
# credentials, so a stub CLI exercises the whole path in CI.

set -euo pipefail
# shellcheck source=deploy/lib.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

local_only=0
case "${1:-}" in
  --local-only) local_only=1 ;;
  "") ;;
  *) echo "usage: deploy/net-check.sh [--local-only]" >&2; exit 2 ;;
esac

target="$(deploy_serve_target)"          # http://127.0.0.1:$RECIPE_DEPLOY_PORT
hostport="${target#http://}"             # 127.0.0.1:$RECIPE_DEPLOY_PORT

fail=0
pass() { printf 'PASS  %s\n' "$*"; }
bad()  { printf 'FAIL  %s\n' "$*"; fail=1; }

# Host part (address without the port) of every LISTEN socket on $1, via `ss`.
# The deployment target is WSL Ubuntu, where `ss` (iproute2) is always present;
# if it is somehow missing this prints nothing and check 2 fails closed rather
# than guessing.
_listen_hosts_on_port() {
  local port="$1"
  command -v ss >/dev/null 2>&1 || return 0
  ss -H -ltn 2>/dev/null | awk -v p=":$port\$" '
    { addr = $4; if (addr ~ p) { sub(/:[0-9]+$/, "", addr); print addr } }'
}

_is_loopback_host() {
  case "$1" in
    127.0.0.1 | "[::1]" | ::1) return 0 ;;
    *) return 1 ;;
  esac
}

echo "== resolved deployment config =="
deploy_print_config
echo

echo "== ingress diagnostics =="

# 1. app answering on loopback
if deploy_http_ok "$target/api/health"; then
  pass "app answers on $hostport (/api/health)"
else
  bad "app not answering on $hostport — start it (deploy/control.sh start)"
fi

# 2. no non-loopback listener on the app port
_hosts="$(_listen_hosts_on_port "$RECIPE_DEPLOY_PORT" | sort -u)"
if [ -z "$_hosts" ]; then
  bad "could not enumerate listeners on port $RECIPE_DEPLOY_PORT (is 'ss' installed?) — cannot confirm loopback-only bind"
else
  _bypass=""
  while IFS= read -r h; do
    [ -n "$h" ] || continue
    _is_loopback_host "$h" || _bypass="$_bypass $h"
  done <<EOF
$_hosts
EOF
  if [ -n "$_bypass" ]; then
    bad "non-loopback listener on port $RECIPE_DEPLOY_PORT:$_bypass — a LAN/public listener is bypassing the Tailscale ingress"
  else
    pass "port $RECIPE_DEPLOY_PORT is bound on loopback only (no LAN/public bypass)"
  fi
fi

if [ "$local_only" -eq 1 ]; then
  echo
  [ "$fail" -eq 0 ] && echo "local checks passed (--local-only; Tailscale checks skipped)" \
                    || echo "local checks FAILED (--local-only)"
  exit "$fail"
fi

# 3. Tailscale up / Running
if _tailscale_status="$(deploy_tailscale status 2>/dev/null)"; then
  if printf '%s\n' "$_tailscale_status" | grep -Eqi 'Tailscale is stopped|Logged out|BackendState.*Stopped'; then
    bad "Tailscale is not running — '$RECIPE_DEPLOY_TAILSCALE_BIN up' and enable unattended operation"
  else
    pass "Tailscale is up on this node"
  fi
else
  bad "'$RECIPE_DEPLOY_TAILSCALE_BIN status' failed — Tailscale CLI missing or daemon down"
fi

# 4. Serve maps the tailnet HTTPS port to the local origin
if _serve_status="$(deploy_tailscale serve status 2>/dev/null)"; then
  if printf '%s\n' "$_serve_status" | grep -q "$hostport"; then
    pass "Serve proxies the tailnet to $target"
  else
    bad "Serve is not pointing at $target — run deploy/tailscale-serve.sh apply"
  fi
else
  bad "'$RECIPE_DEPLOY_TAILSCALE_BIN serve status' failed — cannot confirm the ingress mapping"
fi

# 5. Funnel OFF (and confirmed so)
case "$(deploy_funnel_state)" in
  on)
    bad "Tailscale Funnel is ON — this deployment must be private only ('$RECIPE_DEPLOY_TAILSCALE_BIN funnel reset')" ;;
  unknown)
    bad "could not determine Funnel state ('$RECIPE_DEPLOY_TAILSCALE_BIN funnel status' failed) — cannot confirm there is no public exposure" ;;
  *)
    pass "Funnel is off (no public exposure)" ;;
esac

# 6. tailnet URL resolves
if _url="$(deploy_tailnet_url)"; then
  pass "tailnet HTTPS address: $_url"
  echo
  echo "from a permitted client (Tailscale connected):"
  printf "  curl -sS -o /dev/null -w '%%{http_code}\\\\n' %sapi/health   # expect 200\n" "$_url"
  printf "  curl -sS -o /dev/null -w '%%{http_code}\\\\n' %sapi/recipes   # expect 401 (auth still required)\n" "$_url"
else
  bad "could not read this node's tailnet name ('$RECIPE_DEPLOY_TAILSCALE_BIN status --json' .Self.DNSName)"
fi

echo
[ "$fail" -eq 0 ] && echo "all ingress checks passed" || echo "ingress checks FAILED — see FAIL lines above"
exit "$fail"
