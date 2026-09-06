# 06b — actual-host acceptance results

Ticket: `issues/06b-wsl-lifetime.md` — keep WSL serving after terminals close
(`deploy/wsl-keeper.sh` + `deploy/windows/register-keeper-task.ps1`).

Linux CI proves the mechanism deterministically (`backend/tests/test_deploy.py`,
the `test_keeper_*` cases): `wsl-keeper.sh run` holds the app up and a `SIGTERM`
takes keeper + supervisor + app down together; a second `run` is refused and
duplicates nothing; a terminated supervisor is re-launched on the next heartbeat
and adopts the still-running app; `stop` is clean with nothing up. The checks
below need the real Windows/WSL host — the actual `wsl.exe` invocation, Task
Scheduler, host power behaviour, closing the IDE/terminals, and a real
`wsl --shutdown` — and are **not** satisfied by CI. Fill in
`Result` / `Date` / `By` / `Notes` on the target machine and commit this file.

Runbook: README "Operating the server" #17. Tools: `deploy/wsl-keeper.sh`,
`deploy/windows/register-keeper-task.ps1`. Depends on #16 (`deploy/supervise.sh`).

Scope: this slice keeps the **WSL distribution + app supervisor** alive
independent of a development shell, and recovers after a controlled
`wsl --shutdown`. Starting before an interactive Windows login (full reboot) and
running Tailscale ingress unattended are ticket 06c — a separate acceptance file.

## Host inputs (record actuals — do not assume dev values)

| Input | Value on target host |
| --- | --- |
| WSL distribution (`-Distro`) | _pending_ |
| `RECIPE_DEPLOY_CHECKOUT` (`-Checkout`, path inside WSL) | _pending_ |
| `RECIPE_DEPLOY_PORT` | _pending_ |
| `RECIPE_DEPLOY_DATA_DIR` (holds `recipe-keeper.log`) | _pending_ |
| `RECIPE_DEPLOY_KEEPER_HEARTBEAT` (if not default 30) | _pending_ |
| Scheduled Task name (`-TaskName`) | _pending_ (default `RecipeAppWslKeeper`) |
| Repetition interval (`-RepetitionMinutes`) | _pending_ (default 5) |
| Principal `LogonType` | _pending_ (`S4U`, or `Password` if S4U cannot start WSL) |
| Windows / Task Scheduler version | _pending_ |
| Host power plan + sleep/hibernate timeouts (AC / battery) | _pending_ |
| Laptop lid-close action (if applicable) | _pending_ |

## Checks

| # | Check | Expected | Result | Date | By | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `register-keeper-task.ps1 -Distro … -Checkout …` on the host | task registered; prints the AtLogOn + 5-min repetition triggers, restart-on-failure, S4U logon, and the `wsl.exe … wsl-keeper.sh run` command | PENDING | | | |
| 2 | `Get-ScheduledTask -TaskName <name>` after registration | present, Enabled; AtLogOn trigger for the user with a repetition every `-RepetitionMinutes`; action `wsl.exe -d <distro> -- bash <checkout>/deploy/wsl-keeper.sh run`; settings: no execution time limit, RestartInterval 1 min / RestartCount 999, MultipleInstances IgnoreNew, runs on battery, not idle-stopped; principal LogonType S4U (or Password) | PENDING | | | |
| 3 | `Start-ScheduledTask -TaskName <name>`, then `wsl.exe -d <distro> -- bash <checkout>/deploy/wsl-keeper.sh status` | keeper running; supervisor running; `deploy/control.sh status` healthy on `127.0.0.1:<port>` | PENDING | | | |
| 4 | Close the IDE and **every** development terminal; wait out an idle period while the host stays awake; re-check from a permitted device | app still reachable; a household account signs in; a previously saved recipe/inventory record reads back and a new write persists on reload | PENDING | | | |
| 5 | Terminate the app process (`kill $(cat $RECIPE_DEPLOY_DATA_DIR/run/recipe.pid)`) with WSL still up | the supervisor beneath the keeper restarts it within a few seconds; `GET /api/health` returns; `wsl-keeper.sh status` shows the supervisor running and `app restarts >= 1` | PENDING | | | |
| 6 | Hard-kill the app supervisor loop only (`kill -9 $(cat $RECIPE_DEPLOY_DATA_DIR/run/recipe-supervisor.pid)`), leaving the app running | within one keeper heartbeat `recipe-keeper.log` records "supervisor has gone — re-launching it" and a new supervisor pid appears; the app pid is unchanged (adopted, not duplicated); exactly one uvicorn on `<port>` | PENDING | | | |
| 7 | Controlled WSL restart: `wsl --shutdown` (or `wsl --terminate <distro>`) from Windows, then leave the host idle | within `RestartInterval` / `-RepetitionMinutes` the task re-runs, WSL boots, and the keeper brings the supervisor and app back with no shell opened; `wsl-keeper.sh status` healthy again; saved data intact | PENDING | | | |
| 8 | Repeat #7 a second time, and separately run `register-keeper-task.ps1` again and `Start-ScheduledTask` again while the deployment is up | no second keeper, supervisor, or app at any point; `wsl-keeper.sh run` by hand reports "already keeping WSL up"; exactly one uvicorn on `<port>`; one task of that name | PENDING | | | |
| 9 | `wsl-keeper.sh stop` (or Task Scheduler "End task") | keeper, supervisor, and app all stop; `deploy/control.sh status` exits 3 (stopped); a clean stop is not auto-restarted by the task | PENDING | | | |
| 10 | Diagnostics are useful after #5–#7: inspect `recipe-keeper.log`, `recipe-supervisor.log`, `recipe.log`, and `Get-ScheduledTaskInfo` | keeper log shows heartbeat + re-launch lines with timestamps; supervisor/app logs show their own restart + startup output; `LastRunTime` / `LastTaskResult` reflect the WSL restart; a lifetime vs supervisor vs app fault is distinguishable | PENDING | | | |
| 11 | Host power configured for expected availability: apply the runbook's `powercfg` settings (and lid-close action on a laptop), then leave the host idle on AC for longer than the former sleep timeout | the host does not sleep; the deployment stays reachable throughout | PENDING | | | |
| 12 | Confirm the documented limitation: put the host to sleep manually, then wake it | service is down while asleep and returns after wake (keeper task restart / repetition) — recorded as expected behaviour, not a regression | PENDING | | | |

## Result summary

- Access after closing terminals/IDE + idle (check 4): _pending_
- Recovery after controlled WSL restart (checks 7–8): _pending_
- No duplicate keeper / supervisor / app on repeat (checks 6, 8): _pending_
- Host power behaviour configured for expected availability (checks 11–12): _pending_
- Deviations from the documented behaviour (if any): _pending_

## Sign-off

- Commissioned by: _pending_
- Date: _pending_
