# Phase 7 — Documentation

## Goal

Make repository guidance match the backend that actually shipped.

## Inputs

- [`../spec.md`](../spec.md)
- [`../plan.md`](../plan.md)
- [`../features.md`](../features.md)
- Completed phase files in this directory.

**R-10 read-only exception:** Phase 7 may read `features.md` only to link
deferred work and verify exclusions. It must not implement a deferred feature
or describe one as part of the shipped v1 surface.

## Work

- [x] Update `README.md` with setup, authentication, v1 workflows, API surface,
      LAN serving, and the current frontend limitation.
- [x] Add a single **"Operating the server"** section to `README.md` holding
      three ordered runbooks. All three are the same activity — a human at a
      terminal, server stopped, doing something irreversible — and the ordering
      is exactly what gets lost when they are scattered across three documents:
  - **First-user bootstrap** — start with `RECIPE_ALLOW_REGISTRATION=true` and
    `RECIPE_REGISTRATION_CODE=<code>`, register, **stop the server**, restart
    without them, confirm a second register returns `403`.
  - **Backup** — `sqlite3 recipe.db ".backup 'recipe-$(date +%F).db'"`. Use
    `.backup`, not `cp`: it is safe against a live database. There are no
    migrations, so this is the only thing standing between a schema change and
    total data loss; say so.
  - **Schema reset / restore** — take a backup, stop the server,
    `rm backend/recipe.db`, restart (the lifespan recreates the schema). To
    restore, stop the server and copy a snapshot back over `recipe.db`.
- [x] Update `CLAUDE.md` with the final architecture, transaction ownership
      (`TransactionRoute` owns the commit; `get_db` owns session lifetime),
      app-factory test seam, commands, and schema-reset procedure.
- [x] Update `backend/.env.example` with `RECIPE_SESSION_TTL_DAYS` (note `0`
      is legal and means instantly-expired), `RECIPE_ALLOW_REGISTRATION`, and
      `RECIPE_REGISTRATION_CODE`.
- [x] Point the registration-window and schema-reset references at the
      "Operating the server" section rather than describing a fragment of each
      in place.
- [x] Document that there is no password reset: `POST /api/auth/change-password`
      covers rotation by someone who knows the current password; a forgotten
      password is an operator task against the database file.
- [x] Document that cook deduction and grocery submit are forward-only.
- [x] Document LAN CORS: add the serving frontend's origin to
      `RECIPE_CORS_ORIGINS`, or use `["*"]` only for the trusted,
      non-credentialed LAN deployment.
- [x] Link deferred work to `docs/features.md`; do not restate it.
- [x] Preserve the archive pointer `git show 5144c25:docs/plan.md` for the
      complete pre-trim planning record.
- [x] Remove obsolete references to photo upload, URL import, or nine v1 phases.
      (None found in `README.md`/`CLAUDE.md`/`backend/.env.example` — the only
      hits repo-wide are the legitimate ones in `features.md`, `spec.md`, and
      `decisions.md`.)

## Verification

- [x] `cd backend && uv run pytest` passes.
- [x] The end-to-end `/docs` verification in `spec.md` passes.
- [x] Every command and environment variable in the updated docs is accurate.
- [x] The three "Operating the server" runbooks were executed end to end,
      including a `.backup` and a restore from that snapshot. (`sqlite3` CLI
      was unavailable in the execution sandbox; the backup step used Python's
      `sqlite3` module `Connection.backup()`, the same SQLite online-backup API
      the CLI's `.backup` wraps, and the restored snapshot was verified to
      contain the bootstrapped user.)
- [x] All v1 issues are closed. `docs/issues.md` already reads "No open
      issues" — no diff needed there. (Several `.scratch/backend-v1/issues/
      phase-*.md` tracker files carry a stale `Status:` despite being merged;
      out of this ticket's **Files:** list, so left alone rather than
      corrected here — a separate tracker-hygiene pass, not a phase-7
      documentation change.)

## Exit criteria

- [x] All requirements in [`../plan.md`](../plan.md) are complete.
- [x] Scope fence passed (R-10, [`../plan.md` §Phase scope fence](../plan.md#phase-scope-fence-and-handoff-contract)):
      every shipped-behavior statement traces to the backend or normative spec;
      `features.md` was used only to link deferrals and verify exclusions.
- [x] Diff review gate passed (R-6, [`../plan.md` §Execution rules](../plan.md#execution-rules)):
      a non-author reviewer confirmed every command, env var, and behavior
      statement in the updated docs against the shipped backend and `spec.md`.
      (Two-axis Standards + Spec review via `/code-review` since `main`. Spec
      review caught the frontend-limitation gap fixed above and the
      out-of-scope tracker edits, now reverted. Standards review's other notes
      were judgment calls, not actioned — see ticket Comments.)
- [x] Phase complete; mark v1 complete in the master status table.
