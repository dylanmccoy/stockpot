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

- [ ] Update `README.md` with setup, authentication, v1 workflows, API surface,
      LAN serving, and the current frontend limitation.
- [ ] Add a single **"Operating the server"** section to `README.md` holding
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
- [ ] Update `CLAUDE.md` with the final architecture, transaction ownership
      (`TransactionRoute` owns the commit; `get_db` owns session lifetime),
      app-factory test seam, commands, and schema-reset procedure.
- [ ] Update `backend/.env.example` with `RECIPE_SESSION_TTL_DAYS` (note `0`
      is legal and means instantly-expired), `RECIPE_ALLOW_REGISTRATION`, and
      `RECIPE_REGISTRATION_CODE`.
- [ ] Point the registration-window and schema-reset references at the
      "Operating the server" section rather than describing a fragment of each
      in place.
- [ ] Document that there is no password reset: `POST /api/auth/change-password`
      covers rotation by someone who knows the current password; a forgotten
      password is an operator task against the database file.
- [ ] Document that cook deduction and grocery submit are forward-only.
- [ ] Document LAN CORS: add the serving frontend's origin to
      `RECIPE_CORS_ORIGINS`, or use `["*"]` only for the trusted,
      non-credentialed LAN deployment.
- [ ] Link deferred work to `docs/features.md`; do not restate it.
- [ ] Preserve the archive pointer `git show 5144c25:docs/plan.md` for the
      complete pre-trim planning record.
- [ ] Remove obsolete references to photo upload, URL import, or nine v1 phases.

## Verification

- [ ] `cd backend && uv run pytest` passes.
- [ ] The end-to-end `/docs` verification in `spec.md` passes.
- [ ] Every command and environment variable in the updated docs is accurate.
- [ ] The three "Operating the server" runbooks were executed end to end,
      including a `.backup` and a restore from that snapshot.
- [ ] All v1 issues are closed.

## Exit criteria

- [ ] All requirements in [`../plan.md`](../plan.md) are complete.
- [ ] Scope fence passed (R-10, [`../plan.md` §Phase scope fence](../plan.md#phase-scope-fence-and-handoff-contract)):
      every shipped-behavior statement traces to the backend or normative spec;
      `features.md` was used only to link deferrals and verify exclusions.
- [ ] Diff review gate passed (R-6, [`../plan.md` §Execution rules](../plan.md#execution-rules)):
      a non-author reviewer confirmed every command, env var, and behavior
      statement in the updated docs against the shipped backend and `spec.md`.
- [ ] Phase complete; mark v1 complete in the master status table.
