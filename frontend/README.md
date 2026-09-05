# Recipe App — Frontend

Vite + React + TypeScript SPA. This doc covers building and deploying it to a
household LAN. For local dev, backend commands, and the API surface, see the
root [`README.md`](../README.md).

## Build

```bash
cd frontend
npm install
npm run build     # tsc -b && vite build -> static output in frontend/dist/
```

`dist/` is a plain static bundle (HTML/CSS/JS) — no Node process needed to
serve it.

## Serve it on the LAN

Every network call in the app goes through one `fetch` wrapper
(`src/api/client.ts`) that always requests a **root-relative** path —
`/api/...` — resolved against whatever origin served the page. There's no
build-time backend URL to configure. That means:

- `dist/` and the FastAPI backend must be reachable at the **same origin**
  (same scheme + host + port) as far as the browser is concerned, exactly
  like the dev server's `/api` proxy (`vite.config.ts`) does for `npm run dev`.
- Put a reverse proxy in front that serves the static files and forwards
  `/api/*` to `uvicorn`. A minimal Caddy example (adjust host/port to taste):

  ```
  192.168.1.50:80 {
      handle /api/* {
          reverse_proxy localhost:8000
      }
      handle {
          root * /path/to/frontend/dist
          file_server
          try_files {path} /index.html
      }
  }
  ```

  nginx or any other proxy that can do the same two rules (reverse-proxy
  `/api`, static-serve + SPA-fallback everything else) works equally well.
  `npm run preview` does **not** do this out of the box — it has no `/api`
  proxy of its own — so it isn't a production serving option here.

- Add the address people type into their browser (the proxy's origin, e.g.
  `http://192.168.1.50`) to the backend's `RECIPE_CORS_ORIGINS`
  (`backend/.env`, a JSON list — see root README's "Operating the server").
  Sessions are a bearer token in an `Authorization` header, not a cookie, so
  `allow_credentials=False` (the backend's fixed setting) is fine even with
  multiple origins listed — there's no cookie for a mismatched origin to leak.

## First-user bootstrap

Registration is closed by default and there's no signup UI in a normal build
(`VITE_ENABLE_REGISTER` unset — see `.env.example`). To create the first
account:

1. **Backend** — start it with registration open, per root README's
   "Operating the server → First-user bootstrap":
   ```bash
   cd backend
   RECIPE_ALLOW_REGISTRATION=true RECIPE_REGISTRATION_CODE=<code> \
     uv run uvicorn app.main:app --reload
   ```
2. **Frontend** — build with the register form enabled, then serve that
   build (same-origin proxy setup above):
   ```bash
   cd frontend
   VITE_ENABLE_REGISTER=1 npm run build
   ```
3. Open the SPA, register the account, confirm login works.
4. **Rebuild and redeploy without the flag** — a plain `npm run build` (no
   `VITE_ENABLE_REGISTER`). The signup form disappears from the bundle
   entirely, it isn't just hidden — this is the required step, since the
   default production bundle must ship with no signup UI.
5. Optionally, also close the backend door: restart it with neither
   `RECIPE_ALLOW_REGISTRATION` nor `RECIPE_REGISTRATION_CODE` set
   (`backend/.env.example`'s defaults), then confirm a
   `POST /api/auth/register` returns `403 {"detail": "registration disabled"}`.
   Leaving the backend flag on is harmless as long as the deployed frontend
   has no way to reach the register form.

## Sessions: fixed 30-day window, no refresh

- A login/register token is valid for `RECIPE_SESSION_TTL_DAYS` (default
  `30`) days **from the moment it's issued** — `expires_at = created_at + TTL`.
  There is no sliding expiry and no refresh endpoint: using the app doesn't
  extend a session, and there's nothing client-side to renew one.
- When a token expires, the next request gets `401` and the SPA's client
  drops it (`api/client.ts`'s unauthorized handler), clears the query cache,
  and redirects to `/login?next=<path>` — the user just logs in again.
- To change how long a household session lasts, set `RECIPE_SESSION_TTL_DAYS`
  on the backend before first login (existing tokens keep whatever TTL was in
  effect when they were issued). `0` is legal and means a token that's
  already expired the instant it's issued — useful for testing, not for real
  use.
- `POST /api/auth/change-password` (API-only, no screen yet) revokes every
  session for that user, including the caller's — rotating a password signs
  the whole household out everywhere until they log back in.
