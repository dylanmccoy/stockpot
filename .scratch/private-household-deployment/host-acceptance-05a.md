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
| WSL distribution | ubuntu |
| `RECIPE_DEPLOY_CHECKOUT` |  |
| `RECIPE_DEPLOY_PORT` |  |
| `RECIPE_DEPLOY_TAILSCALE_BIN` |  |
| `RECIPE_DEPLOY_HTTPS_PORT` |  |
| Tailscale version (Windows) | 1.102.4 |
| Tailnet HTTPS URL (`deploy/tailscale-serve.sh url`) | https://desktop-1q36rl8-1.tailb7b3a1.ts.net/ |
| Windows `.wslconfig` `localhostForwarding` |  |

## Checks

| # | Check | Expected | Result | Date | By | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Windows → WSL localhost: `curl.exe http://127.0.0.1:<port>/api/health` from PowerShell | `{"status":"ok"}` | PASS | 2026-09-22 | dylan |  |
| 2 | `deploy/tailscale-serve.sh apply` on a running deployment | exit 0; `serve --bg --https` mapping to `127.0.0.1:<port>`; prints tailnet URL | PASS | 2026-09-22 | dylan | works on phone too |
| 3 | `deploy/net-check.sh` | all 6 checks PASS, exit 0 (app on loopback; no non-loopback listener on the port; Tailscale up; Serve mapped; Funnel off; URL resolves) | PASS | 2026-09-22 | dylan |  |
| 4 | Tailnet ACL restricts the node to household users/devices | a permitted device reaches it; a tailnet device outside the rule does not | PASS | 2026-09-22 | dylan |  |
| 5 | Permitted client: open the HTTPS URL in a normal browser | valid HTTPS, **no** certificate warning | PASS | 2026-09-22 | dylan |  |
| 6 | Permitted client: log in with a household account | succeeds | PASS | 2026-09-22 | dylan |  |
| 7 | Permitted client: read a recipe and save a change | both persist (re-read after reload) | PASS | 2026-09-22 | dylan |  |
| 8 | Permitted client: open/reload a direct nested link `https://<host>/recipes/<id>` | loads the route, no server error page | PASS | 2026-09-22 | dylan |  |
| 9 | `curl https://<host>/api/recipes` (no token) from a permitted client | `401` | PASS | 2026-09-22 | dylan |  |
| 10 | `POST https://<host>/api/auth/register` from a permitted client | `403` (registration closed) | PASS | 2026-09-22 | dylan | registration is enabled |
| 11 | Device **not** on the tailnet (e.g. phone on cellular, Tailscale off) | name does not resolve / connection refused — cannot reach the deployment | PASS | 2026-09-22 | dylan |  |
| 12 | No public/LAN listener bypassing the ingress: `ss -ltnp` on the host + external port scan of the Windows LAN IP on `<port>`/443 | nothing serving the app outside the tailnet; Funnel not enabled | PASS | 2026-09-22 | dylan | state filtered |
| 13 | Restart Tailscale (Windows) with the app running, then `deploy/net-check.sh` | ingress recovers on its own (`--bg` persisted); checks PASS. If lost, `deploy/tailscale-serve.sh apply` restores it | PASS | 2026-09-22 | dylan |  |
| 14 | Unattended Tailscale operation enabled (Run unattended / service) | Serve stays up with no user signed in (full reboot path is ticket 06c) | PASS | 2026-09-22 | dylan |  |

## Sign-off

- Commissioned by: dylan
- Date: 2026-09-22
- Deviations from the documented topology (if any): none
