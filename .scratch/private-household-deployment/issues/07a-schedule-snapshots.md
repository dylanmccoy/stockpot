# 07a: Create daily snapshots without an open terminal

**What to build:** The owner receives automatic daily local snapshots even when no development terminal or app process is running.

**Blocked by:** 04a: Install the WSL app with existing household data.

**Status:** done

- [ ] Schedule the existing real backup operation at least daily for the explicit deployed database and local backup destination. The task can invoke the intended WSL distribution for a bounded backup job independently of app supervision.
      — **built:** `deploy/windows/register-backup-task.ps1` registers a daily Windows Scheduled Task running `wsl.exe -d <distro> -- bash <checkout>/deploy/backup-run.sh` against the explicit `RECIPE_DEPLOY_DB_FILE` → `RECIPE_DEPLOY_BACKUP_DIR`. `deploy/backup-run.sh` is bounded (`timeout $RECIPE_DEPLOY_BACKUP_TIMEOUT`) and touches no app/supervisor/Tailscale — CI proves it snapshots with the app stopped.
      — **host-pending:** actually registering the task on the target host and confirming its trigger/principal — `host-acceptance-07a.md` #1–#2.

- [ ] Exercise the actual scheduler invocation while the app is available and verify a usable timestamped snapshot; also verify a run with the app stopped.
      — **built:** `backend/tests/test_deploy.py` drives `deploy/backup-run.sh` (the command the task runs) as a subprocess: a usable timestamped snapshot with the deployment running, and again with it stopped, each with an `ok` line in `backup-runs.log`.
      — **host-pending:** the invocation *through Windows Task Scheduler* (`Start-ScheduledTask`), app-up and app-stopped — `host-acceptance-07a.md` #3–#5. Per the delivery constraint, CI alone is not evidence of Task Scheduler behavior.

- [ ] Verify the configured task remains available and runs after a Windows reboot without interactive login. Preserve earlier valid snapshots on failure and record the real invocation result.
      — **built:** failure paths covered in CI — a missing database and an uncreatable destination each exit non-zero, log a `FAIL <reason>` line to `backup-runs.log`, and leave every earlier snapshot untouched; the time limit terminates a stuck snapshot the same way. Idempotent re-registration (`-Force`) and `StartWhenAvailable` are in the `.ps1`.
      — **host-pending:** the reboot-without-login run and recorded results — `host-acceptance-07a.md` #9–#12.

- [x] Document schedule, destination, local permissions, and execution diagnostics. Backup freshness reporting and retention controls are added in 07b; automatic app boot is not a blocker.
      — README "Operating the server" runbook 14 (schedule / destination / permissions / run-log table + diagnosis); `deploy.env.example` and `deploy/control.sh status` carry the new inputs; `docs/deployment.md` outline item 5 and `backend/CLAUDE.md` updated.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

## Comments

- Merged via PR [#92](https://github.com/dylanmccoy/stockpot/pull/92)
  (squash `fd8d688`), CI green (`backend`, `frontend`, `integration`,
  `production-smoke`, `deployment`). Branch rebased onto `main` past tickets
  05b/02c first (README runbook renumber 12 → 14).

- Implemented on branch `feat/private-household-deployment-07a`, worktree
  `.claude/worktrees/private-household-deployment-07a`.

- **`deploy/backup-run.sh`** (new) — the one command a scheduler runs: one
  bounded `deploy_snapshot` of `RECIPE_DEPLOY_DB_FILE` into
  `RECIPE_DEPLOY_BACKUP_DIR` via `scripts/backup.py` (online backup facility,
  safe with the app up or down; no app/supervisor/Tailscale contact). Runs the
  snapshot under `timeout $RECIPE_DEPLOY_BACKUP_TIMEOUT` (default 300s). One
  `ok <path>` / `FAIL <reason>` line per run appended to
  `RECIPE_DEPLOY_RUNTIME_DIR/backup-runs.log`. Any failure exits non-zero and
  leaves earlier snapshots untouched (`backup.py` never publishes a partial).

- **`deploy/windows/register-backup-task.ps1`** (new) — registers / removes the
  Windows Scheduled Task: daily at `-Time`, principal `LogonType S4U` (runs
  with no interactive logon, no stored password; `-LogonType Password`
  fallback), `StartWhenAvailable`, 1h `ExecutionTimeLimit`,
  `MultipleInstances IgnoreNew`, idempotent `-Force`. `-ShowCommand` prints the
  `wsl.exe …` invocation for a manual run.

- **`deploy/lib.sh`** — new `RECIPE_DEPLOY_BACKUP_TIMEOUT` (env, default 300)
  and derived `DEPLOY_BACKUP_LOG`; both shown by `deploy/control.sh status`.

- **Tests** — `backend/tests/test_deploy.py` +6 in the `backend` CI job,
  driving `deploy/backup-run.sh` as a subprocess against disposable data:
  snapshot with the app running and with it stopped (usable record + `ok`
  line), failure preserving earlier snapshots (missing database, uncreatable
  destination) with a `FAIL` line, the time limit terminating a stuck snapshot
  (sleeper `uv` stub), and `status` echoing the new inputs. No new CI job —
  deterministic, no Windows/Task Scheduler.

- **Docs** — README "Operating the server" **runbook 14 · Scheduled daily
  backups (unattended)** (runbook 2 forward-ref updated); `deploy/deploy.env.example`
  documents `RECIPE_DEPLOY_BACKUP_TIMEOUT` and the present-tense backup-dir use;
  `docs/deployment.md` outline item 5 and `backend/CLAUDE.md` `backup.py` row
  point at the new scripts.

- **Host acceptance** — `.scratch/private-household-deployment/host-acceptance-07a.md`
  (new): 12-row checklist for the real Task Scheduler registration, the
  app-up / app-down / failure / reboot-without-login runs, and permissions.
  All rows PENDING — no Windows/WSL host in this session. Linux CI (`backend`
  job) is green.

- Reviewed with `/code-review` (Standards + Spec). Findings actioned:
  - **Criterion 2 set back to `[ ]`** (Spec) — "the *actual scheduler
    invocation*" is Windows Task Scheduler, host-pending; CI drives the backup
    script directly. Matches the 05a precedent (every host-dependent AC stays
    unchecked until `host-acceptance-*` rows are filled). Only criterion 4
    (documentation) is ticked.
  - **`deploy/backup-run.sh` output aligned to the sibling scripts** (Standards)
    — `-- ` for progress, `deploy: ...` for the stderr failure; the parsed
    `ok`/`FAIL` log tokens are unchanged. `_log` now warns on stderr if it
    cannot append. Header trimmed.
  - **`register-backup-task.ps1`** (Standards) — WSL-side script path
    single-quoted so a space in `-Checkout` can't split it; dropped
    `-DontStopIfGoingOnBatteries` / `-AllowStartIfOnBatteries` (host power is
    spec item 24, not this slice) — `StartWhenAvailable` already covers a
    missed run.
  - **Tests** (Standards) — the two success tests clear the adoption snapshot
    and assert exactly one file afterwards, dropping a `time.sleep(1.1)` that
    depended on the wall clock to disambiguate same-second snapshot names.
  - **README permissions wording softened** (Spec) — `backup.py`'s `chmod` is
    best-effort (`except OSError: pass`), now stated as such; host-verified in
    acceptance #6.
  - **Deliberately kept:** `set -uo pipefail` (no `-e`) in `backup-run.sh` —
    the control flow inspects `timeout`'s exit code at three points; the
    deviation from the siblings' `set -euo pipefail` is called out in the
    script header. The `timeout`-absent path runs unbounded with a WARNING
    (coreutils `timeout` is always present on the WSL target; Task Scheduler's
    `ExecutionTimeLimit` is the on-host backstop either way).

