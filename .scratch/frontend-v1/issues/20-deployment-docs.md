# 20: Deployment docs

**What to build:** Written operator notes for serving the SPA on the household LAN and bootstrapping the first user.

**Blocked by:** 19. External gate: backend Phase 7 (docs) merged.

**Status:** ready-for-agent

- [ ] LAN serving notes: how to build and serve `dist/`, and adding the serving origin to `RECIPE_CORS_ORIGINS` (token is a header not a cookie, so `allow_credentials=False` is fine).
- [ ] First-user bootstrap: run the backend with `RECIPE_ALLOW_REGISTRATION=true` + `RECIPE_REGISTRATION_CODE`, build the frontend with `VITE_ENABLE_REGISTER=1`, register, then rebuild/redeploy without the flag (and optionally disable the backend flag).
- [ ] The fixed 30-day session and no-refresh behavior documented for operators.
- [ ] A fresh reader can deploy the SPA on the LAN from the notes alone.

**Refs:** `docs/frontend/spec.md` §12; plan Phase 8.
