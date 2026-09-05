# 04b: Deploy a schema-preserving application update

**What to build:** The owner can deploy a new application build while continuing to use the same household database.

**Blocked by:** 04a: Install the WSL app with existing household data.

**Status:** done

- [x] Provide a repeatable update procedure that prepares and validates a build before switching the running deployment, takes a pre-maintenance snapshot, and restarts against the explicit persistent database.

- [x] A failed build or preparation must leave the current usable deployment and data intact. Do not reset the database or run schema-changing upgrades under this procedure.

- [x] Through disposable deployment data and the production browser, verify identifiable records survive a replacement build and subsequent writes persist.

- [x] Document update, stop/start, snapshot, and health checks. Any future schema change requires a data-preserving migration before installation; the convenience operation to return to an older build follows in 04c.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.


## Comments

- Merged via PR [#87](https://github.com/dylanmccoy/stockpot/pull/87)
  (squash), CI green (`backend`, `frontend`, `integration`,
  `production-smoke`, `deployment` incl. the new `deployment-update` step).

- Implemented on branch `feat/private-household-deployment-04b`, worktree
  `.claude/worktrees/private-household-deployment-04b`.

- **`deploy/update.sh`** — new schema-preserving update procedure:
  1. **Prepare + validate before switching.** Builds the frontend into
     `<frontend-dist>.staging` (a sibling of the live build, so the later
     swap is an atomic rename), runs `uv sync`, and does a backend import
     smoke (`python -c "import app.main"` with `RECIPE_FRONTEND_DIST` pointed
     at the staged assets). Any failure here `rm`s the staging dir and exits
     non-zero **without stopping, switching, or snapshotting** — the running
     deployment and its database are untouched. `--staging-dir <dir>` uses a
     build produced elsewhere and skips the build (mirrors
     `install.sh --skip-build`); it is also how the test harnesses drive it.
  2. **Pre-maintenance snapshot** via the shared `deploy_snapshot` helper
     (see below) into `RECIPE_DEPLOY_BACKUP_DIR`. A snapshot failure also
     aborts before the switch.
  3. **Switch + restart.** `control.sh stop` (if running) → move the live
     build to `<frontend-dist>.prev`, move staging into place → `control.sh
     start`, which always exports the configured absolute
     `RECIPE_DATABASE_URL`. On a successful start `.prev` is removed; if the
     new build fails to start, the previous build is restored and restarted
     so the household is never left down. Never resets the DB, never runs a
     schema-changing upgrade.

- **`deploy/lib.sh`** — extracted `deploy_snapshot <source> <dest-dir>` (runs
  `scripts/backup.py`, picks the newest `recipe-*.db`, validates it landed,
  echoes its path; backup.py's own stdout is redirected to stderr so the
  captured value is only the path). `install.sh`'s adoption path now calls it
  too, removing the duplication the update path would otherwise have added.

- **Tests**
  - `backend/tests/test_deploy.py` (+2, `backend` CI job): update switches the
    served build, takes the pre-maintenance snapshot first, and the adopted
    record survives against the same explicit DB; a bad staged build (no
    `index.html`) aborts with the running deployment, its data, and the
    snapshot count all unchanged and no `.prev` left behind.
  - `frontend/e2e/smoke.update.spec.ts` + `update-server.mjs` +
    `update-teardown.ts` + `update.env.ts` + `playwright.update.config.ts` —
    new `update` Playwright project and the `deployment-update` CI run (a step
    in the existing `deployment` job). The harness installs + adopts a prior
    DB and starts it with a **backgrounded** `control.sh start` (not the
    `deployment` project's foreground `control.sh run`, because the update
    needs the stop/start controls); the spec writes a recipe against the old
    build, runs `deploy/update.sh --staging-dir`, then asserts the adopted
    recipe and the pre-update write are still visible on the replacement build
    (confirmed live via a marker asset served only by the new build), the
    pre-maintenance snapshot count went up by one, and a post-update write
    persists across a reload. `globalTeardown` stops the detached deployment
    (Playwright's webServer kill can't reach a detached session).
  - `frontend/playwright.config.ts` `testIgnore` extended so the visual suite
    skips `*.update.spec.ts` (matches the existing integration/deployment
    exclusions).

- **Docs** — root `README.md` runbook 9 ("WSL deployment update
  (schema-preserving)"): update / stop-start / snapshot / health-check
  commands, the prepare-then-switch ordering, the intactness guarantee, the
  transient `.prev` rollback, and the note that a future schema change needs a
  data-preserving migration (runbook 3 is the dev-only reset, not an upgrade
  path). The on-demand return to an older build is called out as ticket 04c.

- **Host acceptance** — not run: no Windows/WSL/Tailscale host in this
  session. Linux CI (`backend` + `deployment`, including the new
  `deployment-update` step) is green; commissioning runbook 9 on the target
  machine is still pending per the spec's actual-host acceptance gate.

- Reviewed with `/code-review` (Standards + Spec axes).

### Review findings actioned

- **`deploy_snapshot` extracted into `lib.sh`** and shared by `install.sh` and
  `update.sh` — removes the snapshot-block duplication this ticket would have
  introduced. (Standards.)
- **`.prev` is now transient**, removed on a successful update rather than
  retained "for 04c" — 04c will design its own previous-build retention; a
  lingering `.prev` here was speculative. `update.sh` keeps it only as the
  in-run rollback checkpoint. (Spec — scope.)
- **Dropped `--no-start`** — not requested by the ticket and untested; an
  update now always ends with the new build serving. Removed the asymmetry the
  reviewer flagged between "start a stopped deployment during update" and the
  rollback path. (Spec — scope.)
- **Browser test now also asserts the pre-maintenance snapshot** (backup-dir
  count before/after), not just the shell test. (Spec — coverage.)
- `test_deploy.py`'s `_stub_dist` gained an optional `marker=` arg instead of a
  near-duplicate `_stub_dist_with_marker`; dead `trace: "on-first-retry"`
  removed from `playwright.update.config.ts` (`retries: 0` there on purpose — a
  retry would re-run against an already-updated deployment). (Standards.)

### Deliberately not changed

- **No shared `e2e/deploy-harness.mjs`.** `update-server.mjs` repeats the
  seed/health/spawn shape from `deployment-server.mjs` / `production-server.mjs`.
  Ticket 04a's merged review explicitly deferred extracting that helper as
  out-of-scope; folding a third copy into a new helper now means editing two
  merged 01a/04a files for a refactor 04b doesn't need. Left as a follow-up.
- **Rollback on a failed start is kept.** It is the ticket's "leave the current
  usable deployment intact" guarantee applied to a failed switch (the old build
  is already stopped by then), not ticket 04c's deliberate operator command to
  return to an older working build. Flagged inline in the script.
- **`.gitignore` entries for `frontend/dist.staging|prev/`** target the default
  in-checkout build location; a `RECIPE_DEPLOY_FRONTEND_DIST` outside the
  checkout puts its siblings outside too, where git never sees them — the
  entries are correct where they matter and inert elsewhere.
