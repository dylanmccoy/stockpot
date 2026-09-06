# 07a — actual-host acceptance results

Ticket: `issues/07a-schedule-snapshots.md` — create daily snapshots without an
open terminal.

Linux CI proves the deterministic half only: `deploy/backup-run.sh` driven as a
subprocess against disposable data (`backend/tests/test_deploy.py`) — a snapshot
with the app running and with it stopped, the run-log lines, failure leaving
earlier snapshots intact, and the time limit terminating a stuck snapshot. The
checks below need the real Windows/WSL host and its Task Scheduler; they are
**not** satisfied by CI. Fill in `Result` / `Date` / `By` / `Notes` on the
target machine and commit this file.

Runbook: README "Operating the server" #12. Tools: `deploy/backup-run.sh`,
`deploy/windows/register-backup-task.ps1`.

## Host inputs (record actuals — do not assume dev values)

| Input | Value on target host |
| --- | --- |
| WSL distribution (`-Distro`) | _pending_ |
| `RECIPE_DEPLOY_CHECKOUT` (`-Checkout`, path inside WSL) | _pending_ |
| `RECIPE_DEPLOY_DB_FILE` | _pending_ |
| `RECIPE_DEPLOY_BACKUP_DIR` | _pending_ |
| `RECIPE_DEPLOY_RUNTIME_DIR` (holds `backup-runs.log`) | _pending_ |
| `RECIPE_DEPLOY_BACKUP_TIMEOUT` | _pending_ (default 300) |
| Scheduled Task name (`-TaskName`) | _pending_ (default `RecipeAppDailyBackup`) |
| Daily run time (`-Time`, host local) | _pending_ (default 03:30) |
| Principal `LogonType` | _pending_ (`S4U`, or `Password` if S4U cannot start WSL) |
| Windows / Task Scheduler version | _pending_ |

## Checks

| # | Check | Expected | Result | Date | By | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `register-backup-task.ps1 -Distro … -Checkout …` on the host | task registered; prints the daily schedule, S4U logon, and the `wsl.exe … backup-run.sh` command | PENDING | | | |
| 2 | `Get-ScheduledTask -TaskName <name>` after registration | present, Enabled; trigger Daily at `-Time`; action `wsl.exe -d <distro> -- bash <checkout>/deploy/backup-run.sh`; settings show StartWhenAvailable, ExecutionTimeLimit 1h, MultipleInstances IgnoreNew; principal LogonType S4U (or Password) | PENDING | | | |
| 3 | `Start-ScheduledTask` with the **deployment app running** | a new `recipe-<UTC>.db` appears in `RECIPE_DEPLOY_BACKUP_DIR`; `backup-runs.log` gains one `ok <path>` line; `Get-ScheduledTaskInfo` `LastTaskResult` = 0 | PENDING | | | |
| 4 | Open the snapshot from check 3 in an isolated app instance (runbook 5) | representative household records readable through a fresh login / API | PENDING | | | |
| 5 | `Start-ScheduledTask` with the **app process stopped** (`deploy/control.sh stop`), WSL still up | snapshot still created; `ok` line logged — the job does not depend on app supervision | PENDING | | | |
| 6 | Snapshot directory + file permissions on the host | backup directory `0700`, each `recipe-*.db` `0600`, owned by the operator account; not under the served asset tree | PENDING | | | |
| 7 | Induce a failure (e.g. rename `RECIPE_DEPLOY_DB_FILE` aside) and `Start-ScheduledTask` | task exits non-zero; `backup-runs.log` gains a `FAIL <reason>` line; **every earlier snapshot still present and unchanged**; no partial file | PENDING | | | |
| 8 | Restore the database name from check 7 and `Start-ScheduledTask` again | back to `ok`; recovery points intact | PENDING | | | |
| 9 | Full Windows reboot; **do not** sign in interactively | after the next scheduled `-Time` (or `StartWhenAvailable` catch-up), a fresh snapshot + `ok` line appear with no one logged in | PENDING | | | |
| 10 | `Get-ScheduledTaskInfo -TaskName <name>` after the reboot day | `LastRunTime` on/after the reboot, `LastTaskResult` = 0, `NextRunTime` set | PENDING | | | |
| 11 | Re-run `register-backup-task.ps1` (repeat setup) | exactly one task of that name remains (idempotent `-Force`); no duplicate triggers | PENDING | | | |
| 12 | Bounded job: confirm `RECIPE_DEPLOY_BACKUP_TIMEOUT` and the task's 1h `ExecutionTimeLimit` are in force | a hung snapshot is terminated and logged `FAIL … time limit`; the task does not stay Running | PENDING | | | |

## Sign-off

- Commissioned by: _pending_
- Date: _pending_
- Deviations from the documented topology (if any): _pending_
