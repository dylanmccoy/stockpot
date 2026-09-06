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
| WSL distribution | _pending_ |
| `RECIPE_DEPLOY_CHECKOUT` | _pending_ |
| `RECIPE_DEPLOY_PORT` | _pending_ |
| `RECIPE_DEPLOY_DATA_DIR` | _pending_ |
| `RECIPE_DEPLOY_KEEPER_SERVE` (set to `1`? or ingress driven from Windows) | _pending_ |
| `RECIPE_DEPLOY_TAILSCALE_BIN` (if not `tailscale.exe`) | _pending_ |
| Task name (if not `RecipeAppWslKeeper`) | _pending_ |
| Principal `LogonType` (`S4U` / `Password`) | _pending_ |
| Registration shell (elevated? or not) | _pending_ |
| Boot trigger attached by the script, or added by hand | _pending_ |
| Tailscale "Run unattended" enabled | _pending_ |
| Host power: standby / hibernate / lid-close settings applied | _pending_ |
| Permitted client used for the pre-login check (device + network) | _pending_ |

## Checks

| # | Check | Expected | Result | Date | By | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Run `register-keeper-task.ps1` (no `-NoBootTrigger`) on the host | task registered; output shows `at boot (before login), at logon`; `verified : at-boot trigger is in force` (no warning), or the warning acted on by hand | PENDING | | | |
| 2 | `Get-ScheduledTask -TaskName RecipeAppWslKeeper` → triggers | an *At startup* trigger plus *At log on* and the repetition; principal `LogonType S4U` (or `Password` per host input) | PENDING | | | |
| 3 | Full reboot (`shutdown /r /t 0`); **stay at the sign-in screen, do not log in**; wait for the host to settle | — | PENDING | | | |
| 4 | From a permitted client (Tailscale connected), open `deploy/tailscale-serve.sh url` — **before** any Windows login | valid HTTPS (no cert warning); app loads | PENDING | | | |
| 5 | Sign in to the app with a household account; open a previously saved recipe | login succeeds; the record reads back unchanged | PENDING | | | |
| 6 | Make an edit and reload the nested route (`/recipes/<id>`) | the change persisted; direct-link reload works (no API error page) | PENDING | | | |
| 7 | `curl https://<host>.<tailnet>.ts.net/api/recipes` from the client; `POST /api/auth/register` | `401` (auth still required); `403` (registration closed) | PENDING | | | |
| 8 | From a device **not** on the tailnet | the name does not resolve; the host cannot be reached — no LAN/public bypass appeared across the reboot | PENDING | | | |
| 9 | Now sign in to Windows; `wsl.exe -d <Distro> -- bash <Checkout>/deploy/wsl-keeper.sh status` | keeper running; app healthy on `127.0.0.1:<port>`; supervisor running | PENDING | | | |
| 10 | Inspect `recipe-keeper.log` | a boot-time `keeper: holding WSL up` line timestamped before the login; with `RECIPE_DEPLOY_KEEPER_SERVE=1`, a `Tailscale ingress is up` line | PENDING | | | |
| 11 | `deploy/net-check.sh` from WSL after the AtLogOn trigger has also fired | all ingress checks pass; exactly one app listener (loopback only) and one Serve mapping — the logon trigger firing on top of the boot-started keeper duplicated nothing | PENDING | | | |
| 12 | Re-run `register-keeper-task.ps1` with the deployment already up, then `Start-ScheduledTask` | `-Force` replaces the task (no duplicate); `MultipleInstances IgnoreNew` + the keeper pidfile mean no second keeper / supervisor / app | PENDING | | | |
| 13 | Reboot again with the machine on battery / left idle (per host availability expectations) | access returns as in checks 4–6; if the host slept, note the power setting that needs changing | PENDING | | | |
| 14 | Failure rehearsal: disable the boot trigger (or block WSL S4U start), reboot, follow the runbook 18 diagnosis table to recover | access restored using only the documented manual steps | PENDING | | | |

## Result summary

- Reboot-without-login result (checks 3–8): _pending_
- Unattended ingress mechanism used (`RECIPE_DEPLOY_KEEPER_SERVE=1` / Windows-side): _pending_
- No-duplicate-instances on retry / repeated setup (checks 11–12): _pending_
- Failure diagnosis + manual recovery rehearsed (check 14): _pending_
- Deviations from the documented behaviour (if any): _pending_

## Sign-off

- Commissioned by: _pending_
- Date: _pending_
