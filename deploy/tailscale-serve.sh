#!/usr/bin/env bash
# Private HTTPS ingress for the household deployment (private-household-
# deployment ticket 05a).
#
#   deploy/tailscale-serve.sh apply | status | url | reset
#
# Configures Windows Tailscale Serve to proxy the deployment's local
# production origin (http://127.0.0.1:$RECIPE_DEPLOY_PORT) out onto the tailnet
# over HTTPS, private to permitted household devices. It does NOT touch the app
# listener — that stays on 127.0.0.1 (deploy/control.sh) — and it never enables
# Funnel or any public exposure.
#
#   apply   — point Serve at the local origin over HTTPS on the tailnet,
#             persistently (`--bg`, so the mapping survives a Tailscale /
#             machine restart). Refuses if Funnel is active or the local
#             origin is not answering. Idempotent: re-running re-asserts the
#             same mapping, which is also the recovery step after a Tailscale
#             restart if the persistent config was ever lost.
#   status  — the current Serve mapping, tailnet node state, and whether
#             Funnel is on (it must not be).
#   url     — print the tailnet HTTPS address household devices open.
#   reset   — clear this node's Serve configuration.
#
# The Tailscale CLI and the tailnet HTTPS port are deploy/lib.sh config
# (RECIPE_DEPLOY_TAILSCALE_BIN, default tailscale.exe for the WSL topology;
# RECIPE_DEPLOY_HTTPS_PORT, default 443). Restricting the tailnet to permitted
# household identities/devices is an admin-console ACL step — it needs tailnet
# admin, not this host — and is covered in README "Operating the server"
# runbook 11. Configure unattended Tailscale operation there too.

set -euo pipefail
# shellcheck source=deploy/lib.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

_target="$(deploy_serve_target)"

_require_local_origin() {
  deploy_http_ok "$_target/api/health" && return 0
  _deploy_die "local origin $_target is not answering /api/health — start the deployment first (deploy/control.sh start)"
}

_refuse_if_funnel() {
  case "$(deploy_funnel_state)" in
    on)
      _deploy_die "Tailscale Funnel is active on this node — this deployment is private only. Run '$RECIPE_DEPLOY_TAILSCALE_BIN funnel reset' first." ;;
    unknown)
      echo "WARNING: could not determine Funnel state ('$RECIPE_DEPLOY_TAILSCALE_BIN funnel status' failed) — continuing, but confirm Funnel is off." >&2 ;;
  esac
}

_apply() {
  _refuse_if_funnel
  _require_local_origin
  echo "-- configuring Tailscale Serve: tailnet :$RECIPE_DEPLOY_HTTPS_PORT (HTTPS) -> $_target"
  # --bg: run in the background and persist the mapping in tailscaled state, so
  # it comes back on its own after a Tailscale or Windows restart.
  deploy_tailscale serve --bg --https="$RECIPE_DEPLOY_HTTPS_PORT" "$_target"
  echo
  _status
  echo
  if url="$(deploy_tailnet_url)"; then
    echo "household devices (Tailscale connected) open:  $url"
  fi
  echo
  echo "WARNING: Serve is now reachable to EVERY device on this tailnet."
  echo "         Before sharing the address, restrict this node to permitted"
  echo "         household identities/devices in the admin-console ACLs, and"
  echo "         enable unattended Tailscale operation — README \"Operating the"
  echo "         server\" runbook 11 steps 3-4. Then run deploy/net-check.sh."
}

_status() {
  echo "== Tailscale Serve =="
  deploy_tailscale serve status || true
  echo
  echo "== tailnet node =="
  deploy_tailscale status || true
  echo
  case "$(deploy_funnel_state)" in
    on)      echo "Funnel           : ON  <-- must not be on for a private deployment" ;;
    unknown) echo "Funnel           : unknown (could not query)" ;;
    *)       echo "Funnel           : off" ;;
  esac
}

_url() {
  url="$(deploy_tailnet_url)" \
    || _deploy_die "could not read this node's tailnet name ('$RECIPE_DEPLOY_TAILSCALE_BIN status --json' .Self.DNSName) — is Tailscale up?"
  printf '%s\n' "$url"
}

_reset() {
  echo "-- clearing Tailscale Serve configuration on this node"
  deploy_tailscale serve reset
  echo "cleared"
}

case "${1:-}" in
  apply) _apply ;;
  status) _status ;;
  url) _url ;;
  reset) _reset ;;
  *) echo "usage: deploy/tailscale-serve.sh {apply|status|url|reset}" >&2; exit 2 ;;
esac
