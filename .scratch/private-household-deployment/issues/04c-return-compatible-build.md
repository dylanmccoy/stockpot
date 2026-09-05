# 04c: Return to a previous compatible app build

**What to build:** The owner can recover from an unsuitable application update by selecting a previous compatible build without rolling back household records.

**Blocked by:** 04b: Deploy a schema-preserving application update.

**Status:** in-review

- [x] Retain or identify a previous compatible build and provide an operator operation to switch the app back using the existing deployment controls and current persistent database.

- [x] Validate the selected build and compatibility before switching; a missing or unusable selection must not destroy the running build or data.

- [x] Create a record after an update, return to the previous compatible build, and verify that record remains readable and editable through the production browser.

- [x] Document application-build rollback separately from snapshot data restore. Do not imply that an older build can safely run against an incompatible future schema.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.


## Comments

- Implemented on branch `feat/private-household-deployment-04c`, worktree
  `.claude/worktrees/private-household-deployment-04c`.

- **`deploy/rollback.sh`** — new deliberate operator command to return the
  deployment to a previously retained frontend build:
  - `deploy/rollback.sh --list` — retained builds, newest first.
  - `deploy/rollback.sh` — return to the most recently retained build.
  - `deploy/rollback.sh --to <timestamp>` — a specific retained build by name.
  - `deploy/rollback.sh --to <dir>` — a build directory the operator identified
    themselves (the "or identify" half of AC1).
  - **Validate before switching (AC2).** Resolves the selection, then checks
    `index.html` + a backend import smoke against it *before* stopping anything.
    A missing / unknown / unusable selection `_deploy_die`s with the running
    deployment, its data, and the snapshot count all untouched.
  - **Pre-maintenance snapshot** via the shared `deploy_snapshot` helper; a
    snapshot failure also aborts before the switch (spec item 11 "Take a backup
    before potentially data-affecting maintenance").
  - **Switch + restart (AC1).** The shared `deploy_switch_build` helper stages
    the selected build, stops, swaps it in with two atomic renames, and starts
    via `deploy/control.sh`, which always exports the one configured absolute
    `RECIPE_DATABASE_URL` — the current persistent database, never reset, no
    schema step. On a failed start the build that was running is restored and
    restarted. Rollback is one-directional: moving forward again is a
    `deploy/update.sh` build.

- **`deploy/update.sh`** — on a successful update the build it replaces is now
  copied into the build archive (`deploy_archive_build`) instead of being
  discarded; that is what `rollback.sh` returns to. An archive failure warns but
  does not fail the update (the new build is already serving). Its validation
  and switch blocks now call the shared `deploy_validate_build` /
  `deploy_switch_build`.

- **`deploy/lib.sh`** — new config `RECIPE_DEPLOY_BUILD_ARCHIVE` (default
  `RECIPE_DEPLOY_DATA_DIR/builds`) + `RECIPE_DEPLOY_BUILD_KEEP` (default 5),
  absolutised and printed by `deploy_print_config`. New helpers:
  `deploy_validate_build`, `deploy_retained_builds`, `deploy_archive_build`
  (copy into `<archive>/<UTC timestamp>/`, prune to the newest `KEEP`), and
  `deploy_switch_build` (stage → stop → atomic swap → start, restore-on-failed-
  start) — the last two extracted so `update.sh` and `rollback.sh` share the
  switch/restart/abort sequence rather than duplicating ~40 lines.

- **Tests**
  - `backend/tests/test_deploy.py` (+3, `backend` CI job): rollback returns to
    the retained build and the adopted record survives against the same
    explicit DB with a pre-maintenance snapshot taken; a bad / unknown / unusable
    selection aborts with the running deployment, its data, the snapshot count,
    and `.prev` all unchanged; `--list` reports retained builds.
  - `frontend/e2e/smoke.update.spec.ts` (+1 test in the existing `update`
    Playwright project / `deployment-update` CI run): with the updated build
    live, write a recipe, run `deploy/rollback.sh`, then assert the pre-update
    build is served again (marker asset 404), a pre-maintenance snapshot was
    taken, and every record — seed + the one written against the updated build
    + one written after rollback — is readable and editable through the browser
    (AC3). No new CI step; the file's header now covers 04b + 04c.

- **Docs (AC4)** — root `README.md` runbook 10 ("WSL deployment rollback"):
  documents build rollback as **distinct from** snapshot data restore
  (runbook 5), the validate-then-switch ordering, the intact-on-bad-selection
  guarantee, the one-directional nature, and the warning that an older build
  must not run against a newer migrated schema (no migration path exists yet;
  runbook 3 is the dev-only reset). Runbook count 9 -> 10; runbook 9's
  forward-reference to "ticket 04c" updated.

- **Host acceptance** — not run: no Windows/WSL/Tailscale host in this session.
  Linux CI (`backend` + `deployment` incl. `deployment-update`) is green;
  commissioning runbook 10 on the target machine is still pending per the
  spec's actual-host acceptance gate.

- Reviewed with `/code-review` (Standards + Spec axes). Findings actioned:

  - **Extracted `deploy_switch_build`** into `lib.sh`, shared by `update.sh` and
    `rollback.sh` — removes the ~40-line switch/restart/abort duplication the
    reviewer flagged as Shotgun Surgery. The helper stages the incoming build
    and swaps with two atomic renames, closing the gap where a swap failure
    (bad copy, or `--to` the live dir) could leave the deployment stopped.
  - **Dropped roll-forward archiving from `rollback.sh`.** The ticket asks only
    to *return to* a previous build; archiving the build rolled away from was
    unrequested. Moving forward is a `deploy/update.sh` build.
  - **Collision-safe archive names.** `deploy_archive_build`'s same-second
    suffix is now a zero-padded `-NN`, which stays within the chronological
    lexical sort `deploy_retained_builds` depends on (was `-$$`, a PID that
    could sort a colliding build ahead of a genuinely newer one).
  - **`deploy_archive_build` prune reuses `deploy_retained_builds`** instead of
    repeating the `find | sort`.
  - **README runbook 10** no longer claims a migration lives in runbook 9
    (none exists); matches `update.sh`'s "runbook 3 is the dev-only reset"
    phrasing. Clarified that "compatible" = same schema era and that the
    serveable-build check is not a schema check.

- **Deliberately not changed**

  - **`smoke.update.spec.ts` carries the 04c browser test.** Both review axes
    flagged it as a judgement call, not a blocker. Splitting it into
    `smoke.rollback.spec.ts` breaks Playwright's file ordering (it would sort
    before `smoke.update.spec.ts` and run without a retained build); renaming
    the merged `update` project / CI job is churn on 04b files for no behaviour
    change. The test needs 04b's end-state (a retained build) to exist, so it
    is co-located, ordered after the update test, and the file header now
    covers both tickets.
  - **No schema-vs-DB compatibility check in `rollback.sh`.** Spec item 11
    states no schema change ships in this deployment and that migration
    infrastructure "is not a prerequisite". The only compatibility dimension
    that exists now — is this a structurally valid build this backend can
    serve — is what `deploy_validate_build` checks; the schema dimension is an
    operator-owned doc gate (runbook 10), by the spec's design.
