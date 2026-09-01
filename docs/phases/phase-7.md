# Phase 7 — Documentation

## Goal

Make repository guidance match the backend that actually shipped.

## Inputs

- [`../spec.md`](../spec.md)
- [`../plan.md`](../plan.md)
- [`../features.md`](../features.md)
- Completed phase files in this directory.

## Work

- [ ] Update `README.md` with setup, authentication, v1 workflows, API surface,
      LAN serving, and the current frontend limitation.
- [ ] Update `CLAUDE.md` with the final architecture, transaction ownership,
      app-factory test seam, commands, and schema-reset procedure.
- [ ] Update `backend/.env.example` with `RECIPE_SESSION_TTL_DAYS`,
      `RECIPE_ALLOW_REGISTRATION`, and `RECIPE_REGISTRATION_CODE`.
- [ ] Document the temporary registration-window procedure.
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
- [ ] All v1 issues are closed.

## Exit criteria

- [ ] All requirements in [`../plan.md`](../plan.md) are complete.
- [ ] Phase complete; mark v1 complete in the master status table.
