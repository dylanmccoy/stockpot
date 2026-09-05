# 20: Deployment docs

**What to build:** Written operator notes for serving the SPA on the household LAN and bootstrapping the first user.

**Blocked by:** 19a, 19b. External gate: backend Phase 7 (docs) merged.

**Status:** in-review

**Files:** create / edit `frontend/README.md` (or `docs/frontend/deployment.md`). No `frontend/src/` changes. External gate: backend Phase 7 merged.

**Spec:** `docs/frontend/spec.md` §12 (definition of done — deployment docs); `docs/spec.md` §3.1 (`RECIPE_*` env vars), §5.1 (registration window). Read only these sections.

**Tests:** None (docs only) — a fresh reader can deploy the SPA on the LAN from the notes alone.

- [x] LAN serving notes: how to build and serve `dist/`, and adding the serving origin to `RECIPE_CORS_ORIGINS` (token is a header not a cookie, so `allow_credentials=False` is fine).
- [x] First-user bootstrap: run the backend with `RECIPE_ALLOW_REGISTRATION=true` + `RECIPE_REGISTRATION_CODE`, build the frontend with `VITE_ENABLE_REGISTER=1`, register, then rebuild/redeploy without the flag (and optionally disable the backend flag).
- [x] The fixed 30-day session and no-refresh behavior documented for operators.
- [x] A fresh reader can deploy the SPA on the LAN from the notes alone.

**Refs:** `docs/frontend/spec.md` §12; plan Phase 8.

## Comments

- Implemented on `docs/frontend-v1-20`, worktree
  `.claude/worktrees/frontend-v1-20`. Added `frontend/README.md`: build, LAN
  serving (same-origin reverse-proxy requirement — the client only ever
  fetches root-relative `/api/...`, so `npm run preview` alone can't serve a
  production deploy), first-user bootstrap (backend flag + `VITE_ENABLE_REGISTER`
  build, then rollback of both), and the fixed 30-day/no-refresh session
  behavior. No `frontend/src/` changes; no test changes (docs-only ticket).
