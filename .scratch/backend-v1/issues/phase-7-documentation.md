# phase-7: Documentation

**What to build:** Repository guidance (`README.md`, `CLAUDE.md`,
`backend/.env.example`) matches the backend that shipped, the operating runbooks
live in one place and were executed for real, and no stale references remain.

**Blocked by:** `phase-6f` (backend feature-complete).

**R-10 read-only exception:** Phase 7 may read `docs/features.md` only to link
deferred work and verify exclusions. It must not implement a deferred feature or
describe one as shipped v1 surface.

**Status:** done

**Files:** edit `README.md`, `CLAUDE.md`, `backend/.env.example`, `docs/phases/phase-7.md`, `docs/plan.md`. Read `docs/features.md` only to link deferrals.

**Spec:** `docs/spec.md` "End-to-end verification (via `/docs`)", §3.1 (`config.py` env vars), §5.1 (registration window). Read only these sections.

**Tests:** `cd backend && uv run pytest`, plus the `/docs` end-to-end verification in `docs/spec.md`.

- [x] `README.md` updated with setup, authentication, v1 workflows, API surface,
      LAN serving, and the current frontend limitation.
- [x] A single **"Operating the server"** section in `README.md` holding three
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
- [x] The three runbooks executed end to end, including a `.backup` and a restore
      from that snapshot.
- [x] `CLAUDE.md` updated with the final architecture, transaction ownership
      (`TransactionRoute` owns the commit; `get_db` owns session lifetime),
      app-factory test seam, commands, and the schema-reset procedure.
- [x] `backend/.env.example` updated with `RECIPE_SESSION_TTL_DAYS` (note `0` is
      legal and means instantly-expired), `RECIPE_ALLOW_REGISTRATION`, and
      `RECIPE_REGISTRATION_CODE`.
- [x] Registration-window and schema-reset references point at "Operating the
      server" rather than restating a fragment in place.
- [x] Documented: no password reset (`POST /api/auth/change-password` covers
      known-password rotation; a forgotten password is an operator task against
      the database file); cook deduction and grocery submit are forward-only;
      LAN CORS (add the serving frontend's origin to `RECIPE_CORS_ORIGINS`, or
      `["*"]` only for a trusted non-credentialed LAN deployment).
- [x] Deferred work linked to `docs/features.md`, not restated; the archive
      pointer `git show 5144c25:docs/plan.md` preserved; obsolete references to
      photo upload, URL import, or nine v1 phases removed (none found in the
      edited files to begin with).
- [x] Verification: `cd backend && uv run pytest` green; the end-to-end `/docs`
      verification in `spec.md` passes; every command and env var in the updated
      docs is accurate; all v1 issues closed.
- [x] Phase 7 exit criteria in `docs/phases/phase-7.md`: R-10 scope fence (every
      shipped-behavior statement traces to the backend or normative spec;
      `features.md` used only to link deferrals and verify exclusions); R-6
      diff-review gate (a non-author reviewer confirmed every command, env var,
      and behavior statement against the shipped backend and `spec.md`).
- [x] `docs/plan.md`: mark **v1 complete** in the master status table.

## Comments

- 2026-09-04: Implemented on `docs/backend-v1-phase-7`, worktree
  `.claude/worktrees/backend-v1-phase-7`.
  - All three "Operating the server" runbooks executed for real against a live
    `uv run uvicorn` instance: first-user bootstrap (register → `201`, restart
    without the two env vars → second register `403`), backup, and schema
    reset/restore (post-reset `SELECT count(*) FROM users` → `0`; restored
    snapshot's user logged in successfully via `/api/auth/login` afterwards).
    `sqlite3` CLI was unavailable in the execution sandbox; the backup step
    used Python's `sqlite3` module `Connection.backup()` — the same SQLite
    online-backup API the CLI's `.backup` wraps — and the restored snapshot
    was verified to contain the bootstrapped user. README documents the
    standard `sqlite3` CLI form for real deployments.
  - R-6 diff-review gate run as a two-axis review (`/code-review` since
    `main`, Standards + Spec sub-agents). Spec review caught two real issues,
    both fixed: (1) README's frontend paragraph overclaimed full integration —
    corrected to note `change-password` has no frontend screen (intentional;
    `frontend/src/types.ts` carries the type, unused) and that registration is
    gated behind `VITE_ENABLE_REGISTER`; (2) this pass had also flipped eight
    `.scratch/backend-v1/issues/phase-{4a,4b,4c,4d,6c,6d,6e,6f}-*.md` tracker
    files' stale `Status:` to `done` — those files aren't in this ticket's
    **Files:** list, so reverted; left for a separate tracker-hygiene pass.
    Standards review's other notes (a documented-vs-baseline duplication
    judgment call in `CLAUDE.md`, and `done` not appearing in
    `triage-labels.md`'s role table) were judgment calls, not hard violations,
    and not actioned — the former matches root `CLAUDE.md`'s existing
    per-app one-line-summary pattern, the latter is a different labeling
    surface (GitHub triage roles vs. this tracker's own `Status:` vocabulary).
