# phase-7: Documentation

**What to build:** Repository guidance (`README.md`, `CLAUDE.md`,
`backend/.env.example`) matches the backend that shipped, the operating runbooks
live in one place and were executed for real, and no stale references remain.

**Blocked by:** `phase-6f` (backend feature-complete).

**R-10 read-only exception:** Phase 7 may read `docs/features.md` only to link
deferred work and verify exclusions. It must not implement a deferred feature or
describe one as shipped v1 surface.

**Status:** ready-for-agent

- [ ] `README.md` updated with setup, authentication, v1 workflows, API surface,
      LAN serving, and the current frontend limitation.
- [ ] A single **"Operating the server"** section in `README.md` holding three
      ordered runbooks:
  - **First-user bootstrap** — start with `RECIPE_ALLOW_REGISTRATION=true` and
    `RECIPE_REGISTRATION_CODE=<code>`, register, **stop the server**, restart
    without them, confirm a second register returns `403`.
  - **Backup** — `sqlite3 recipe.db ".backup 'recipe-$(date +%F).db'"`; state why
    `.backup` not `cp` (safe against a live database), and that with no
    migrations this is the only thing between a schema change and total data
    loss.
  - **Schema reset / restore** — take a backup, stop the server,
    `rm backend/recipe.db`, restart (the lifespan recreates the schema); to
    restore, stop the server and copy a snapshot back over `recipe.db`.
- [ ] The three runbooks executed end to end, including a `.backup` and a restore
      from that snapshot.
- [ ] `CLAUDE.md` updated with the final architecture, transaction ownership
      (`TransactionRoute` owns the commit; `get_db` owns session lifetime),
      app-factory test seam, commands, and the schema-reset procedure.
- [ ] `backend/.env.example` updated with `RECIPE_SESSION_TTL_DAYS` (note `0` is
      legal and means instantly-expired), `RECIPE_ALLOW_REGISTRATION`, and
      `RECIPE_REGISTRATION_CODE`.
- [ ] Registration-window and schema-reset references point at "Operating the
      server" rather than restating a fragment in place.
- [ ] Documented: no password reset (`POST /api/auth/change-password` covers
      known-password rotation; a forgotten password is an operator task against
      the database file); cook deduction and grocery submit are forward-only;
      LAN CORS (add the serving frontend's origin to `RECIPE_CORS_ORIGINS`, or
      `["*"]` only for a trusted non-credentialed LAN deployment).
- [ ] Deferred work linked to `docs/features.md`, not restated; the archive
      pointer `git show 5144c25:docs/plan.md` preserved; obsolete references to
      photo upload, URL import, or nine v1 phases removed.
- [ ] Verification: `cd backend && uv run pytest` green; the end-to-end `/docs`
      verification in `spec.md` passes; every command and env var in the updated
      docs is accurate; all v1 issues closed.
- [ ] Phase 7 exit criteria in `docs/phases/phase-7.md`: R-10 scope fence (every
      shipped-behavior statement traces to the backend or normative spec;
      `features.md` used only to link deferrals and verify exclusions); R-6
      diff-review gate (a non-author reviewer confirmed every command, env var,
      and behavior statement against the shipped backend and `spec.md`).
- [ ] `docs/plan.md`: mark **v1 complete** in the master status table.
