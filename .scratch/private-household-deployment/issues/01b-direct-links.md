# 01b: Reload bookmarked pages without breaking API errors

**What to build:** A household member can open or reload a bookmarked recipe or inventory page while API failures and missing assets retain correct responses.

**Blocked by:** 01a: Open and use the built app at its entry address.

**Status:** done

- [x] Add frontend route fallback so direct loading and reloading a nested route, including the login route, works with the production build.

- [x] Give API routes precedence. Unknown API requests preserve their HTTP status and API response format, and missing static assets return a missing-resource response rather than the SPA document.

- [x] Through the production browser harness, test direct nested navigation, session hydration after reload, and invalid-session redirection; verify unknown API and missing-asset responses via the same origin.

- [x] Keep static-file confinement tests green and add focused boundary/traversal cases for the new fallback. Document direct-link behavior as part of the serving instructions.

## Comments

- Merged via PR [#80](https://github.com/dylanmccoy/stockpot/pull/80)
  (squash), CI green (`backend`, `frontend`, `production-smoke`).

- Implemented on `feat/private-household-deployment-01b`, worktree at
  `.claude/worktrees/private-household-deployment-01b`.
- `main.py::_mount_frontend` adds a catch-all `GET /{full_path:path}` after
  every other route: any path whose first segment isn't `api` or `assets`
  gets `index.html` (letting `react-router`'s `<BrowserRouter>` own client
  routing, including its own `NotFound`); `api`/`assets` explicitly 404
  rather than falling back, so an unknown API path keeps the plain JSON 404
  and a missing/renamed asset never gets the SPA document even if the
  `/assets` mount itself doesn't exist. The fallback never resolves
  `full_path` against the filesystem, so it can't be used to escape the
  build directory.
- `backend/tests/test_frontend_serving.py`: new cases for the client-side
  fallback, unknown-API 404, and a fallback traversal boundary case
  (percent-encoded `..`, since plain `..` gets collapsed client-side by
  `httpx`/`TestClient` before it ever reaches the server); updated the
  existing confinement test to use percent-encoded traversal for the same
  reason. Full backend suite green.
- `frontend/e2e/smoke.production.spec.ts`: new "direct links (01b)" describe
  block — direct nested-route load while anonymous, direct `/login` load,
  session hydration on reload, invalid-stored-token redirect to login,
  unknown-API 404, missing-asset 404. All 12 production-suite scenarios pass
  locally (`npm run build && npm run test:e2e:production`).
- `README.md` "Operating the server" #4 and `backend/CLAUDE.md`'s file map
  updated for the new fallback behavior.
- Ran `/code-review` (Standards + Spec axes) against `main`: no blocking
  findings on either axis. Standards flagged two judgement-call smells
  (magic strings `"api"`/`"assets"`, a stale docstring first line) — fixed
  both with a clarifying comment and an updated summary line.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

