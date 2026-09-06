# 07c: Recover the deployed app from a scheduled snapshot

**What to build:** The owner can follow a complete deployment recovery procedure and regain usable household data within one day.

**Blocked by:** 07a: Create daily snapshots without an open terminal; 02c: Restore an existing database safely while stopped.

**Status:** in-review

- [x] Combine installed deployment controls and existing validated restore operations into a concrete runbook: select a successful scheduled snapshot, stop writers, preserve the target, restore, restart, and check app access.
      — **built:** README "Operating the server" **runbook 15** — `select` (newest `ok` line in `backup-runs.log`, 07a) → `deploy/control.sh stop` → `scripts/restore.py --replace --preserve-dir` (02c) → `deploy/control.sh start` + `status` + `deploy/net-check.sh` → fresh-login / representative-read / old-session / post-snapshot-change checks. Runbook 13 cross-links it; `docs/deployment.md` outline item 5 and `backend/CLAUDE.md` updated.

- [x] First execute the procedure against a separate deployment database and isolated production app instance, leaving live household data untouched.
      — **built:** `backend/tests/test_deploy.py` +2 (`backend` CI job) drive the whole runbook against the isolated `deploy_env` deployment — its own port, data/backup/runtime dirs, and app process: seed via API (registration briefly open), `deploy/backup-run.sh` for the scheduled snapshot, diverge, `scripts/restore.py --replace`, restart with registration closed. `test_recovery_selects_the_newest_good_scheduled_snapshot` exercises the runbook's `backup-runs.log` selection step over a mixed `ok`/`FAIL` log. No stray database under the checkout; the scheduled snapshot is only read.

- [ ] Use a scheduled snapshot no more than 24 hours old; verify representative restored records through a fresh browser login, rejection of restored old sessions, and absence of changes made after the snapshot.
      — **built (CI, not the whole AC):** the tests restore from a `deploy/backup-run.sh` snapshot and verify **over real HTTP against the running production deployment** — fresh `POST /api/auth/login` reads back the pre-snapshot recipe, `GET /api/auth/me` with a token captured before the restore is `401`, the post-snapshot recipe is absent.
      — **host-pending:** a **real browser** on a permitted device and a **real** scheduled snapshot with its age recorded (< 24h). Per the 07a precedent a host-dependent AC stays unchecked until the `host-acceptance-*` rows are filled — here `host-acceptance-07c.md` #3, #8.

- [ ] Record an actual-host recovery rehearsal completed within one day. State the accepted dependence on usable local snapshots and a surviving disk; keep off-machine backups and disk-loss recovery deferred.
      — **built:** the accepted dependence and the deferred scope (off-machine backups, disk/machine-loss recovery — spec items 13, 30) are stated in runbook 15 and in `host-acceptance-07c.md` ("Accepted dependence" section + sign-off).
      — **host-pending:** the **timed** actual-host rehearsal itself — `host-acceptance-07c.md` #1–#12, all rows PENDING (no Windows/WSL host in this session). Per the delivery constraint, CI is not evidence of a completed one-day recovery on the target machine.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

## Comments

- Implemented on branch `feat/private-household-deployment-07c`, worktree
  `.claude/worktrees/private-household-deployment-07c`.

- **No new runtime code.** 07c composes the tools its blockers shipped —
  `deploy/backup-run.sh` (07a), `scripts/restore.py --replace` +
  `app.restore.replace_database` (02c), `deploy/control.sh` (04a/06a) — into
  one procedure and proves the composition.

- **`README.md`** — new **runbook 15 · Recover the deployment from a scheduled
  snapshot**: select the newest `ok` line in `backup-runs.log` → `control.sh
  stop` → `restore.py --replace --preserve-dir` → `control.sh start` /
  `status` / `net-check.sh --local-only` → fresh-login + representative-read +
  old-session + post-snapshot-change checks. States the accepted dependence
  (usable local snapshot + surviving disk) and the deferred scope (off-machine
  backups, disk-loss recovery). Runbook 13 forward-links it.

- **`backend/tests/test_deploy.py`** — +2 tests in the `backend` CI job,
  reusing the `deploy_env` fixture (isolated port / data / backup / runtime /
  app process):
  - `test_recover_deployment_from_a_scheduled_snapshot` — seed via API with
    registration briefly open, `deploy/backup-run.sh` for the scheduled
    snapshot, add a post-snapshot recipe, `stop` → `restore.py --replace` →
    `start` with registration closed, `net-check.sh --local-only`. Over real
    HTTP against the running deployment: fresh login reads back
    `Pre-snapshot Stew`, the pre-restore token is `401`, `Post-snapshot Pie`
    is gone, `register` is `403`, the scheduled snapshot is byte-unchanged, no
    `backend/recipe.db`.
  - `test_recovery_selects_the_newest_good_scheduled_snapshot` — one good
    `backup-run.sh` then one that FAILs (database moved aside); the runbook's
    `awk` selector picks the newest `ok` path; `restore.py --replace` from it
    rolls the divergence back and keeps the replaced database as a recovery
    point.
  - New helpers: `_recipe_row` (shared by `_seed_db` + `_add_recipe_row`),
    `_api`/`_register`/`_create_recipe`/`_titles_via_http` (HTTP against the
    running deployment), `_restore_replace`. New imports: `json`, `sys`.

- **`.scratch/private-household-deployment/host-acceptance-07c.md`** (new) —
  12-row **timed** rehearsal checklist (start/stop the clock, one-day target),
  an "Accepted dependence" section, and sign-off fields for the elapsed time,
  the snapshot age, and the deferred-scope acknowledgement. All rows PENDING —
  no Windows/WSL host in this session.

- **Docs** — `docs/deployment.md` outline item 5 and `backend/CLAUDE.md`
  `restore.py` row point at runbook 15 / this ticket.

- CI: `cd backend && uv run pytest` green (full suite, 5× under
  `pytest-randomly`); `test_deploy.py` green.

- Reviewed with `/code-review` (Standards + Spec). Actioned:
  - **Criterion 3 reverted to `[ ]`** (Spec) — it asks for a *browser* login
    and a *real* scheduled snapshot ≤24h old; CI proves the mechanics over
    HTTP with a zero-age snapshot. Matches 07a (host-dependent AC stays
    unchecked until `host-acceptance-*` is filled).
  - **Added `test_recovery_selects_the_newest_good_scheduled_snapshot`** (Spec)
    — the `backup-runs.log` selection step (the one thing 07c adds over 02c)
    was not exercised; it now is, over a mixed `ok`/`FAIL` log.
  - **`net-check.sh --local-only` added to the happy-path test** (Spec) — it
    is a runbook step and was missing from the CI path.
  - **`_recipe_row` extracted** (Standards: Duplicated Code) — `_add_recipe_row`
    and `_seed_db` shared the `insert(models.Recipe).values(...)` column list.
  - **Runbook 15 "verify in a browser" trimmed** from 3 mentions to 1 bullet
    plus the standard test/host-gate note (Standards: repetition).
  - **Replaced the earlier `test_recovery_keeps_..._recovery_point`** whose
    "unrelated earlier snapshot untouched" assertion re-covered
    `test_replace.py` (Spec: duplicate coverage).
  - **Deliberately skipped:** `_restore_replace` mirrors the per-file
    subprocess `_run` shape in `test_restore_cli.py` — cross-file test-helper
    sharing was consciously declined in 02c and is out of this slice's scope;
    `_titles_via_http` vs `_recipe_titles` are the HTTP and sqlite readers,
    kept distinct on purpose.

