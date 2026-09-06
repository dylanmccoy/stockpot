# 05a — actual-host acceptance results

Ticket: `issues/05a-private-https.md` — private HTTPS ingress (Tailscale Serve).

Linux CI proves the deterministic half only (scripts + stub Tailscale CLI, see
`backend/tests/test_deploy.py`). The checks below need the real Windows/WSL host,
a real tailnet, and a second device; they are **not** satisfied by CI. Fill in
`Result` / `Date` / `By` / `Notes` on the target machine and commit this file.

Runbook: README "Operating the server" #11. Tools: `deploy/tailscale-serve.sh`,
`deploy/net-check.sh`.

## Host inputs (record actuals — do not assume dev values)

| Input | Value on target host |
| --- | --- |
| WSL distribution | _pending_ |
| `RECIPE_DEPLOY_CHECKOUT` | _pending_ |
| `RECIPE_DEPLOY_PORT` | _pending_ |
| `RECIPE_DEPLOY_TAILSCALE_BIN` | _pending_ |
| `RECIPE_DEPLOY_HTTPS_PORT` | _pending_ |
| Tailscale version (Windows) | _pending_ |
| Tailnet HTTPS URL (`deploy/tailscale-serve.sh url`) | _pending_ |
| Windows `.wslconfig` `localhostForwarding` | _pending_ |

## Checks

| # | Check | Expected | Result | Date | By | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Windows → WSL localhost: `curl.exe http://127.0.0.1:<port>/api/health` from PowerShell | `{"status":"ok"}` | PENDING | | | |
| 2 | `deploy/tailscale-serve.sh apply` on a running deployment | exit 0; `serve --bg --https` mapping to `127.0.0.1:<port>`; prints tailnet URL | PENDING | | | |
| 3 | `deploy/net-check.sh` | all 6 checks PASS, exit 0 (app on loopback; no non-loopback listener on the port; Tailscale up; Serve mapped; Funnel off; URL resolves) | PENDING | | | |
| 4 | Tailnet ACL restricts the node to household users/devices | a permitted device reaches it; a tailnet device outside the rule does not | PENDING | | | |
| 5 | Permitted client: open the HTTPS URL in a normal browser | valid HTTPS, **no** certificate warning | PENDING | | | |
| 6 | Permitted client: log in with a household account | succeeds | PENDING | | | |
| 7 | Permitted client: read a recipe and save a change | both persist (re-read after reload) | PENDING | | | |
| 8 | Permitted client: open/reload a direct nested link `https://<host>/recipes/<id>` | loads the route, no server error page | PENDING | | | |
| 9 | `curl https://<host>/api/recipes` (no token) from a permitted client | `401` | PENDING | | | |
| 10 | `POST https://<host>/api/auth/register` from a permitted client | `403` (registration closed) | PENDING | | | |
| 11 | Device **not** on the tailnet (e.g. phone on cellular, Tailscale off) | name does not resolve / connection refused — cannot reach the deployment | PENDING | | | |
| 12 | No public/LAN listener bypassing the ingress: `ss -ltnp` on the host + external port scan of the Windows LAN IP on `<port>`/443 | nothing serving the app outside the tailnet; Funnel not enabled | PENDING | | | |
| 13 | Restart Tailscale (Windows) with the app running, then `deploy/net-check.sh` | ingress recovers on its own (`--bg` persisted); checks PASS. If lost, `deploy/tailscale-serve.sh apply` restores it | PENDING | | | |
| 14 | Unattended Tailscale operation enabled (Run unattended / service) | Serve stays up with no user signed in (full reboot path is ticket 06c) | PENDING | | | |

## Sign-off

- Commissioned by: _pending_
- Date: _pending_
- Deviations from the documented topology (if any): _pending_
