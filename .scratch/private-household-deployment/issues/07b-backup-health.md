# 07b: Report backup freshness and manage local retention

**What to build:** The owner can tell whether backups meet the 24-hour target and retain useful recovery points on local disk.

**Blocked by:** 07a: Create daily snapshots without an open terminal.

**Status:** done

- [x] Expose the latest successful snapshot, its age, and the latest failed attempt through an operator-facing status command or report. Explicitly flag no successful backup or a success older than 24 hours.
      — **built:** `scripts/backup_status.py` (operator CLI, run from `backend/` like `scripts/backup.py`) reports the latest valid snapshot + its age, the count of valid snapshots, and the latest `FAIL` line from `backup-runs.log`. It prints `STALE` to stderr and exits non-zero when there is no successful backup on disk, or the latest success is older than `RECIPE_DEPLOY_BACKUP_MAX_AGE_HOURS` (default 24) — the exit status is the whole signal, no hosted alerting. `app.backup_status.gather()` is the logic; `--now` injects the clock.

- [x] Provide a documented retention policy with explicit configuration. Retention must preserve required valid recovery points and must not remove earlier successes merely because a new backup failed.
      — **built:** `RECIPE_DEPLOY_BACKUP_KEEP` (env, default 14) in `deploy/lib.sh` + `deploy.env.example`; echoed by `deploy/control.sh status`. `scripts/backup_status.py --prune` (and `deploy/backup-run.sh` after every successful snapshot) keeps the newest KEEP valid snapshots and deletes older ones. Count-based on purpose: a failed run publishes no snapshot, so `valid[keep:]` never grows on failure and an earlier success is never evicted. Documented in README "Operating the server" runbook 14 and `docs/deployment.md` item 5.

- [x] Exercise unwritable-destination, missed/overdue run, incomplete-snapshot, and failed-retention cases; the report must not count incomplete files as successful backups.
      — **built:** `backend/tests/test_backup_status.py` — a missing/uncreatable backup directory is an input error (exit 2); a snapshot older than the target and a directory with no success both flag `STALE` (the missed/overdue run); a hidden `.recipe-*.db.tmp` and a torn `recipe-*.db` are listed but never counted as `latest_success` and never pruned; a delete that fails (read-only directory) is reported, exits non-zero, and leaves the retained set intact. `deploy/backup-run.sh`'s existing unwritable-destination path is unchanged.

- [x] Test deterministic status/retention behavior through the real operator operation with controlled disposable snapshots and time inputs, without requiring a live scheduled wait. Document diagnosis and retry; do not add a hosted alerting service.
      — **built:** `test_backup_status.py` drives `scripts/backup_status.py` as a subprocess and `app.backup_status` directly against disposable snapshot directories with an injected `--now` / `now=` — latest-success age, the flags, incomplete-not-counted, count-based retention, dry-run, and the failed-delete report. `test_deploy.py::test_backup_run_applies_retention_after_a_successful_snapshot` drives the prune through `deploy/backup-run.sh` end to end. Diagnosis + retry are README runbook 14 ("Diagnosis" bullets: fix the last `FAIL` cause, re-run `deploy/backup-run.sh` / `Start-ScheduledTask`, re-check; a prune-permission warning → fix the directory, re-run `--prune`). No hosted alerting — the CLI exit status is the signal.
      — **host-pending:** confirming the scheduled job's prune runs through the real `wsl.exe` + host `uv`, and the report against the real backup dir / `backup-runs.log` — `host-acceptance-07b.md` #1–#7 (all PENDING; no Windows/WSL host in this session).

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

## Comments

- Merged via PR [#94](https://github.com/dylanmccoy/stockpot/pull/94)
  (squash `b5b761b`), CI green (`backend`, `frontend`, `integration`,
  `production-smoke`, `deployment`).

- Implemented on branch `feat/private-household-deployment-07b`, worktree
  `.claude/worktrees/private-household-deployment-07b`.

- **`backend/app/backup_status.py`** (new) — leaf module (stdlib only, no ORM).
  `gather(dest_dir, log_path, now, keep, max_age) -> BackupReport`: parses
  `recipe-<UTC>.db` names for snapshot times, opens each read-only
  (`integrity_check` + `recipes` table) to sort valid / `unreadable`, lists
  hidden `.tmp` files as `incomplete`, and reads the last `FAIL` line from the
  run log. `BackupReport.problem` is the one-line flag (no success / older than
  `max_age`). `prune(...)` deletes `valid[keep:]` only — never a partial, an
  unrelated file, or the log — and captures a delete that raises without
  touching the retained set.

- **`backend/scripts/backup_status.py`** (new) — operator CLI mirroring
  `scripts/backup.py` / `scripts/restore.py`: `--dest-dir` / `--log` /
  `--keep` / `--max-age-hours` / `--prune` / `--dry-run` / `--now` / `--quiet`.
  Exit 0 fresh, 1 stale or no success on disk, 2 bad input or a failed delete.

- **`deploy/backup-run.sh`** — after `_log ok`, `_prune_retention` runs
  `scripts/backup_status.py --prune --quiet`; a prune problem only warns (the
  snapshot already succeeded), it never fails the job.

- **`deploy/lib.sh`** + **`deploy/deploy.env.example`** — `RECIPE_DEPLOY_BACKUP_KEEP`
  (14) and `RECIPE_DEPLOY_BACKUP_MAX_AGE_HOURS` (24); both shown by
  `deploy/control.sh status` (`backup retention` / `backup freshness` lines).

- **Tests** — `backend/tests/test_backup_status.py` (new, 18) + 1 new test in
  `test_deploy.py`, all in the `backend` CI job. `cd backend && uv run pytest`
  green; `shellcheck deploy/*.sh` clean.

- **Docs** — README "Operating the server" runbook 14 gains a "Check freshness
  & apply retention — `scripts/backup_status.py`" subsection + summary-table
  rows + Diagnosis bullets; runbook 2 forward-ref updated; `docs/deployment.md`
  item 5 and `backend/CLAUDE.md` (`backup_status.py` row) updated.

- **Host acceptance** — `host-acceptance-07b.md` (new): 7-row checklist for the
  real Windows/WSL host (scheduled prune through `wsl.exe` + `uv`, report vs
  the real backup dir / run log, staleness flag, failed-retention). All rows
  PENDING.

- **Review** — two-axis (`/code-review`) run inline after the parallel
  sub-agents hit a transient session rate-limit. Standards: no hard
  violations; layering + CLI shape match siblings. Two judgement calls
  actioned — (1) a comment marking `_looks_like_backup` as a deliberate
  lighter cousin of `restore._validate_snapshot` (bool classifier vs raising
  overwrite-gate; sharing would couple status → restore); (2) wired
  `RECIPE_DEPLOY_BACKUP_MAX_AGE_HOURS` into `backup-run.sh`'s prune call so the
  config is not defined-but-unused. Spec: all four criteria met, no scope
  creep, host confirmation properly deferred.
