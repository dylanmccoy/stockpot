# 06c — actual-host acceptance results

Ticket: `issues/06c-windows-boot.md` — restore private access after a Windows
boot without the owner signing in.

Linux CI proves only the deterministic slice (`backend/tests/test_deploy.py` —
the keeper re-asserts Tailscale Serve when `RECIPE_DEPLOY_KEEPER_SERVE` is set
and never touches the CLI when it is not; the no-duplicate-instances guarantees
are the ticket 06b keeper cases). The at-boot Task Scheduler trigger, `wsl.exe`
starting WSL before an interactive logon, real Tailscale unattended mode, and
the reboot-without-login check itself need the real Windows/WSL host and are
**not** satisfied by CI. Fill in `Result` / `Date` / `By` / `Notes` on the
target machine and commit this file.

Runbook: README "Operating the server" #18 (with #17 for the keeper and #11 for
the ingress). Tools: `deploy/windows/register-keeper-task.ps1`,
`deploy/wsl-keeper.sh`, `deploy/tailscale-serve.sh`, `deploy/net-check.sh`.

Scope: this slice is the **boot-before-login** path only. Keeping WSL alive
after terminals close is ticket 06b (`host-acceptance-06b.md`); app-process
restart is 06a; the private ingress itself is 05a.

## Host inputs (record actuals — do not assume dev values)

| Input | Value on target host |
| --- | --- |
| WSL distribution | ubuntu |
| `RECIPE_DEPLOY_CHECKOUT` |  |
| `RECIPE_DEPLOY_PORT` | 8000 |
| `RECIPE_DEPLOY_DATA_DIR` |  |
| `RECIPE_DEPLOY_KEEPER_SERVE` (set to `1`? or ingress driven from Windows) | 1 |
| `RECIPE_DEPLOY_TAILSCALE_BIN` (if not `tailscale.exe`) |  |
| Task name (if not `RecipeAppWslKeeper`) |  |
| Principal `LogonType` (`S4U` / `Password`) | s4u |
| Registration shell (elevated? or not) | elevated |
| Boot trigger attached by the script, or added by hand | script |
| Tailscale "Run unattended" enabled | yes |
| Host power: standby / hibernate / lid-close settings applied | https://desktop-1q36rl8-1.tailb7b3a1.ts.net/ |
| Permitted client used for the pre-login check (device + network) | iphone, cellular, tailscale on |

## Checks

| # | Check | Expected | Result | Date | By | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Run `register-keeper-task.ps1` (no `-NoBootTrigger`) on the host | task registered; output shows `at boot (before login), at logon`; `verified : at-boot trigger is in force` (no warning), or the warning acted on by hand | PASS | 2026-09-22 | dylan |  |
| 2 | `Get-ScheduledTask -TaskName RecipeAppWslKeeper` → triggers | an *At startup* trigger plus *At log on* and the repetition; principal `LogonType S4U` (or `Password` per host input) | PASS | 2026-09-22 | dylan | MSFT_TaskBootTrigger + MSFT_TaskLogonTrigger (user dylan) + MSFT_TaskTimeTrigger (5-min repetition); Principal LogonType S4U, RunLevel Limited |
| 3 | Full reboot (`shutdown /r /t 0`); **stay at the sign-in screen, do not log in**; wait for the host to settle | — | PASS | 2026-09-22 | dylan | LastBootUpTime 2026-09-22 02:09:51 |
| 4 | From a permitted client (Tailscale connected), open `deploy/tailscale-serve.sh url` — **before** any Windows login | valid HTTPS (no cert warning); app loads | PASS | 2026-09-22 | dylan |  |
| 5 | Sign in to the app with a household account; open a previously saved recipe | login succeeds; the record reads back unchanged | PASS | 2026-09-22 | dylan |  |
| 6 | Make an edit and reload the nested route (`/recipes/<id>`) | the change persisted; direct-link reload works (no API error page) | PASS | 2026-09-22 | dylan |  |
| 7 | `curl https://<host>.<tailnet>.ts.net/api/recipes` from the client; `POST /api/auth/register` | `401` (auth still required); `403` (registration closed) | PASS | 2026-09-22 | dylan |  |
| 8 | From a device **not** on the tailnet | the name does not resolve; the host cannot be reached — no LAN/public bypass appeared across the reboot | PASS | 2026-09-22 | dylan |  |
| 9 | Now sign in to Windows; `wsl.exe -d <Distro> -- bash <Checkout>/deploy/wsl-keeper.sh status` | keeper running; app healthy on `127.0.0.1:<port>`; supervisor running | PASS | 2026-09-22 | dylan | keeper pid 345, supervisor pid 829, app pid 695, GET /api/health OK |
| 10 | Inspect `recipe-keeper.log` | a boot-time `keeper: holding WSL up` line timestamped before the login; with `RECIPE_DEPLOY_KEEPER_SERVE=1`, a `Tailscale ingress is up` line | PASS | 2026-09-22 | dylan | `06:10:19Z keeper: holding WSL up (pid 345...)`, 28s after boot, pre-login. No explicit "ingress is up" line — `_ensure_ingress` only logs when it has to re-apply; Serve's `--bg` mapping had already persisted across the reboot (same mechanism as 05a #13), so it stayed silent. net-check.sh independently confirmed the mapping was live pre-login. |
| 11 | `deploy/net-check.sh` from WSL after the AtLogOn trigger has also fired | all ingress checks pass; exactly one app listener (loopback only) and one Serve mapping — the logon trigger firing on top of the boot-started keeper duplicated nothing | PASS | 2026-09-22 | dylan | all 6 checks PASS, exit 0 |
| 12 | Re-run `register-keeper-task.ps1` with the deployment already up, then `Start-ScheduledTask` | `-Force` replaces the task (no duplicate); `MultipleInstances IgnoreNew` + the keeper pidfile mean no second keeper / supervisor / app | PASS | 2026-09-22 | dylan | no duplicates after re-registration |
| 13 | Reboot again with the machine on battery / left idle (per host availability expectations) | access returns as in checks 4–6; if the host slept, note the power setting that needs changing | SKIPPED | 2026-09-22 | dylan |  |
| 14 | Failure rehearsal: disable the boot trigger (or block WSL S4U start), reboot, follow the runbook 18 diagnosis table to recover | access restored using only the documented manual steps | SKIPPED | 2026-09-22 | dylan |  |

## Result summary

- Reboot-without-login result (checks 3–8): confirmed — full HTTPS access, login, edit, reload, 401/403, and off-tailnet unreachability all held before any Windows login
- Unattended ingress mechanism used (`RECIPE_DEPLOY_KEEPER_SERVE=1` / Windows-side): `RECIPE_DEPLOY_KEEPER_SERVE=1`; ingress was already persisted by Tailscale's own `--bg` Serve mapping across the reboot, so the keeper's re-assert path wasn't exercised this run
- No-duplicate-instances on retry / repeated setup (checks 11–12): confirmed — one listener/one Serve mapping after the logon trigger also fired; no duplicate after re-running `register-keeper-task.ps1 -Force`
- Failure diagnosis + manual recovery rehearsed (check 14): not run this pass (optional, deferred)
- Deviations from the documented behaviour (if any): none

## Sign-off

- Commissioned by: dylan
- Date: 2026-09-22
