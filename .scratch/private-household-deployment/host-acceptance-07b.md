# 07b — actual-host acceptance results

Ticket: `issues/07b-backup-health.md` — report backup freshness and manage
local retention.

Linux CI (`backend` job) proves the deterministic core:
`backend/tests/test_backup_status.py` drives `app.backup_status` and
`scripts/backup_status.py` against disposable snapshot directories with an
injected clock (latest-success age, the no-success and older-than-24h flags,
incomplete files never counted as a success, count-based retention, a failed
delete reported without touching the retained set), and
`backend/tests/test_deploy.py` drives `deploy/backup-run.sh` end to end
including the post-success prune. The checks below need the real Windows/WSL
host — the scheduled job invoking the prune through `wsl.exe` + the host `uv`,
and the report reading the real backup directory and `backup-runs.log`. They
are **not** satisfied by CI. Fill in `Result` / `Date` / `By` / `Notes` on the
target machine and commit this file.

Runbook: README "Operating the server" #14 ("Check freshness & apply
retention"). Tools: `scripts/backup_status.py`, `deploy/backup-run.sh`.

## Host inputs (record actuals)

| Input | Value on target host |
| --- | --- |
| `RECIPE_DEPLOY_BACKUP_DIR` | _pending_ |
| `RECIPE_DEPLOY_RUNTIME_DIR` (holds `backup-runs.log`) | _pending_ |
| `RECIPE_DEPLOY_BACKUP_KEEP` | _pending_ (default 14) |
| `RECIPE_DEPLOY_BACKUP_MAX_AGE_HOURS` | _pending_ (default 24) |

## Checks

| # | Check | Expected | Result | Date | By | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | After a real scheduled/`Start-ScheduledTask` run, `uv run python scripts/backup_status.py --dest-dir <dir> --log <log>` on the host | exit 0; `latest success` is the snapshot just taken with an age well under 24h; `latest failure` shows the last `FAIL` line (or "none recorded"); `status : OK` | PENDING | | | |
| 2 | Let the newest good snapshot age past `RECIPE_DEPLOY_BACKUP_MAX_AGE_HOURS` (or pass `--now` a day ahead) and re-run the report | exit 1; `STALE` on stderr naming the age vs the target | PENDING | | | |
| 3 | Move/rename the live DB aside, run `deploy/backup-run.sh`, then the report | job logs `FAIL`; report still shows the previous good snapshot as `latest success` and the new `FAIL` as `latest failure`; **no earlier snapshot removed** | PENDING | | | |
| 4 | Restore the DB name, accumulate more than `RECIPE_DEPLOY_BACKUP_KEEP` successful runs (or pre-seed dated snapshot files), run `deploy/backup-run.sh` | after the run exactly `RECIPE_DEPLOY_BACKUP_KEEP` `recipe-*.db` files remain — the newest ones; the run log shows `ok`; any prune warning is only a warning (exit 0) | PENDING | | | |
| 5 | Drop a hidden `.recipe-*.db.tmp` and a truncated `recipe-*.db` into the backup dir, run the report | both listed as not counted; `latest success` unchanged; neither file pruned by a following `--prune` | PENDING | | | |
| 6 | Make one retained `recipe-*.db` undeletable by the operator account, run `scripts/backup_status.py --prune` | exit 2; the failed delete is named on stderr; every retained snapshot still present | PENDING | | | |
| 7 | `deploy/control.sh status` on the host | shows `backup retention :` and `backup freshness :` lines with the host's configured values | PENDING | | | |

## Sign-off

- Commissioned by: _pending_
- Date: _pending_
- Deviations from the documented topology (if any): _pending_
