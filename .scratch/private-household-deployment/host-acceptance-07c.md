# 07c — actual-host acceptance results

Ticket: `issues/07c-restore-scheduled-snapshot.md` — recover the deployed app
from a scheduled snapshot within one day.

Linux CI proves the procedure mechanically only: `backend/tests/test_deploy.py`
drives the whole runbook 15 path against the isolated `deploy_env` deployment
(its own port, data/backup/runtime dirs, app process) — seed records,
`deploy/backup-run.sh` for the scheduled snapshot, a post-snapshot change,
`scripts/restore.py --replace`, restart, then over real HTTP: a fresh login
sees the snapshot's records, the pre-restore session is `401`, the
post-snapshot change is gone, and the database that was replaced is kept as a
recovery point. The checks below need the **real Windows/WSL host, a real
scheduled snapshot, and a real browser**, and they must be **timed** — they are
**not** satisfied by CI. Fill in `Result` / `Date` / `By` / `Notes` on the
target machine and commit this file.

Runbook: README "Operating the server" #15 (building on #13 in-place replace and
#14 scheduled backups). Prerequisites: `host-acceptance-07a.md` (a real
scheduled snapshot exists) and `host-acceptance-02c.md` equivalents PASS; the
#11 ingress live for the browser check.

Tools: `deploy/backup-run.sh`, `deploy/control.sh`, `scripts/restore.py
--replace`, `deploy/net-check.sh`.

## Accepted dependence (state explicitly in sign-off)

- Recovery depends on **a usable local snapshot** in `RECIPE_DEPLOY_BACKUP_DIR`
  and **a surviving host disk**. With both, the target is ≤24h of lost changes
  (spec item 35) and ≤1 day to restore service (item 36).
- **Deferred, not covered here:** off-machine / cloud backups, and recovery
  from host-disk loss or machine loss (spec item 13; parent spec "Out of
  Scope"). A snapshot older than 24h is already past the data-loss target —
  freshness reporting is ticket 07b.

## Host inputs (record actuals — do not assume dev values)

| Input | Value on target host |
| --- | --- |
| WSL distribution | _pending_ |
| `RECIPE_DEPLOY_CHECKOUT` | _pending_ |
| `RECIPE_DEPLOY_DB_FILE` | _pending_ |
| `RECIPE_DEPLOY_BACKUP_DIR` | _pending_ |
| `RECIPE_DEPLOY_RUNTIME_DIR` (holds `backup-runs.log`) | _pending_ |
| `RECIPE_DEPLOY_DATA_DIR/pre-restore` (preserve dir used) | _pending_ |
| Scheduled snapshot restored from (path + UTC timestamp) | _pending_ |
| Snapshot age at restore time | _pending_ (must be < 24h) |
| Permitted browser device + browser/version used for #8 | _pending_ |
| Tailnet HTTPS URL | _pending_ |

## Checks

| # | Check | Expected | Result | Date | By | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | **Start the clock.** Note wall-clock start of the rehearsal | recorded; the whole rehearsal (#2–#9) completes within one day | PENDING | | | |
| 2 | Make a distinguishable change through the app (e.g. a recipe titled `post-snapshot-<time>`), then note it is *after* the newest `ok` line in `backup-runs.log` | change saved; its timestamp is after the chosen snapshot's | PENDING | | | |
| 3 | Select the snapshot: newest `ok <path>` in `RECIPE_DEPLOY_RUNTIME_DIR/backup-runs.log`; confirm age < 24h | a real `deploy/backup-run.sh` snapshot, < 24h old, chosen | PENDING | | | |
| 4 | `deploy/control.sh stop` | app stops; nothing is writing `RECIPE_DEPLOY_DB_FILE` | PENDING | | | |
| 5 | `scripts/restore.py --replace --snapshot <chosen> --target $RECIPE_DEPLOY_DB_FILE --preserve-dir $RECIPE_DEPLOY_DATA_DIR/pre-restore` | `restore ok: replaced …` + `preserved prior database: …`, exit 0; a preserved copy of the pre-restore database exists in `pre-restore/` | PENDING | | | |
| 6 | `deploy/control.sh start` then `deploy/control.sh status` | starts against the same explicit DB; `GET /api/health` OK | PENDING | | | |
| 7 | `deploy/net-check.sh --local-only` (and full `net-check.sh` if the tailnet is up) | listener still loopback-only; no LAN/public bypass | PENDING | | | |
| 8 | In a browser on a permitted device via the tailnet HTTPS URL: fresh login; read a representative recipe/inventory record from before the snapshot; look for the #2 change; use a session/token captured before the restore | login succeeds; pre-snapshot record reads back; the #2 post-snapshot change is **absent**; the pre-restore session returns to the login screen (`401`) | PENDING | | | |
| 9 | `POST /api/auth/register` against the recovered deployment | `403` — registration still closed | PENDING | | | |
| 10 | **Stop the clock.** Elapsed time from #1 | within one day; record the actual elapsed time | PENDING | | | |
| 11 | Earlier snapshots in `RECIPE_DEPLOY_BACKUP_DIR` and the chosen snapshot file after the restore | all present and unchanged (snapshot only read) | PENDING | | | |
| 12 | The preserved pre-restore copy from #5 | opens as a valid database and still contains the #2 change — a bad snapshot choice is recoverable | PENDING | | | |

## Sign-off

- Rehearsal completed within one day: _pending (state elapsed time)_
- Snapshot used and its age at restore: _pending_
- Accepted dependence acknowledged (usable local snapshot + surviving disk;
  off-machine backup and disk-loss recovery deferred): _pending_
- Commissioned by: _pending_
- Date: _pending_
- Deviations from runbook 15 (if any): _pending_
