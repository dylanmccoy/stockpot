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
| WSL distribution (`-Distro`) | ubuntu |
| `RECIPE_DEPLOY_CHECKOUT` (`-Checkout`, path inside WSL) |  |
| `RECIPE_DEPLOY_DB_FILE` |  |
| `RECIPE_DEPLOY_BACKUP_DIR` |  |
| `RECIPE_DEPLOY_RUNTIME_DIR` (holds `backup-runs.log`) |  |
| `RECIPE_DEPLOY_BACKUP_TIMEOUT` |  |
| Scheduled Task name (`-TaskName`) |  |
| Daily run time (`-Time`, host local) |  |
| Principal `LogonType` | s4u |
| Windows / Task Scheduler version | 2SH2 |

## Checks

| # | Check | Expected | Result | Date | By | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `register-backup-task.ps1 -Distro … -Checkout …` on the host | task registered; prints the daily schedule, S4U logon, and the `wsl.exe … backup-run.sh` command | PASS | 2026-09-22 | dylan |  |
| 2 | `Get-ScheduledTask -TaskName <name>` after registration | present, Enabled; trigger Daily at `-Time`; action `wsl.exe -d <distro> -- bash <checkout>/deploy/backup-run.sh`; settings show StartWhenAvailable, ExecutionTimeLimit 1h, MultipleInstances IgnoreNew; principal LogonType S4U (or Password) | PASS | 2026-09-22 | dylan |  |
| 3 | `Start-ScheduledTask` with the **deployment app running** | a new `recipe-<UTC>.db` appears in `RECIPE_DEPLOY_BACKUP_DIR`; `backup-runs.log` gains one `ok <path>` line; `Get-ScheduledTaskInfo` `LastTaskResult` = 0 | PASS | 2026-09-22 | dylan |  |
| 4 | Open the snapshot from check 3 in an isolated app instance (runbook 5) | representative household records readable through a fresh login / API | PASS | 2026-09-22 | dylan |  |
| 5 | `Start-ScheduledTask` with the **app process stopped** (`deploy/control.sh stop`), WSL still up | snapshot still created; `ok` line logged — the job does not depend on app supervision | PASS | 2026-09-22 | dylan |  |
| 6 | Snapshot directory + file permissions on the host | backup directory `0700`, each `recipe-*.db` `0600`, owned by the operator account; not under the served asset tree | PASS | 2026-09-22 | dylan |  |
| 7 | Induce a failure (e.g. rename `RECIPE_DEPLOY_DB_FILE` aside) and `Start-ScheduledTask` | task exits non-zero; `backup-runs.log` gains a `FAIL <reason>` line; **every earlier snapshot still present and unchanged**; no partial file | PASS | 2026-09-22 | dylan |  |
| 8 | Restore the database name from check 7 and `Start-ScheduledTask` again | back to `ok`; recovery points intact | PASS | 2026-09-22 | dylan |  |
| 9 | Full Windows reboot; **do not** sign in interactively | after the next scheduled `-Time` (or `StartWhenAvailable` catch-up), a fresh snapshot + `ok` line appear with no one logged in | PASS | 2026-09-22 | dylan |  |
| 10 | `Get-ScheduledTaskInfo -TaskName <name>` after the reboot day | `LastRunTime` on/after the reboot, `LastTaskResult` = 0, `NextRunTime` set | PASS | 2026-09-22 | dylan | reboot at 02:09:51; LastRunTime 16:28:29 (20:28:30Z in backup-runs.log), LastTaskResult 0, NextRunTime 2026-09-23 03:30:00 |
| 11 | Re-run `register-backup-task.ps1` (repeat setup) | exactly one task of that name remains (idempotent `-Force`); no duplicate triggers | PASS | 2026-09-22 | dylan |  |
| 12 | Bounded job: confirm `RECIPE_DEPLOY_BACKUP_TIMEOUT` and the task's 1h `ExecutionTimeLimit` are in force | a hung snapshot is terminated and logged `FAIL … time limit`; the task does not stay Running | PASS | 2026-09-22 | dylan |  |

## Sign-off

- Commissioned by: dylan
- Date: 2026-09-22
- Deviations from the documented topology (if any): none
