# 01a: Open and use the built app at its entry address

**What to build:** A household member can open the production entry address, sign in, and save a recipe through the real API without development servers.

**Blocked by:** None (can start immediately).

**Status:** in-review

- [x] Add opt-in built-frontend serving through the existing application factory, preserving API-only operation. Use an explicit build location and report missing required build artifacts clearly.

- [x] Serve the entry document and public build assets beside the existing API. Keep API success/error responses unchanged and confine file serving to the build assets from the first slice; never expose configuration, databases, or checkout contents.

- [x] Extend the existing Playwright real-backend approach to boot this production mode with a disposable file-backed database and dedicated owned processes. Test login from the entry page, wrong-password rejection, logout, a recipe write/read, and refusal of unauthenticated API access.

- [x] Seed accounts before closing registration for assertions; the normal frontend build offers no signup. Add the deterministic production smoke scenario to CI and document its local start command. Direct loading of client-side routes is delivered in 01b.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

## Comments

- Implemented on `feat/private-household-deployment-01a`, worktree at
  `.claude/worktrees/private-household-deployment-01a`.
- `Settings.frontend_dist` (unset by default) + `create_app`'s `_mount_frontend`
  serve `dist/index.html` at `/` and `dist/assets/*`; fails fast with a clear
  `RuntimeError` if the configured location has no `index.html`. Covered by
  `backend/tests/test_frontend_serving.py`.
- New Playwright project `playwright.production.config.ts` boots the built
  frontend behind a real backend via `e2e/production-server.mjs`: seeds one
  account on a throwaway port with registration open, then relaunches on the
  real port with registration closed + `RECIPE_FRONTEND_DIST` set. Scenarios
  in `e2e/smoke.production.spec.ts`: login, wrong password, logout, recipe
  write/read, unauthenticated API refusal, registration-closed. Wired into CI
  as the `production-smoke` job; local start command documented in
  `README.md` "Operating the server" #4 and root `CLAUDE.md`'s command table.
- Ran `/code-review` (Standards + Spec axes) against `main`: no blocking
  findings on either axis. Applied the two cheap documentation fixes it
  suggested in `production-server.mjs`; left its other two minor notes
  (assets-dir leniency, disposable-db path not being in a temp dir) as
  deliberate, non-blocking for this slice's scope.

