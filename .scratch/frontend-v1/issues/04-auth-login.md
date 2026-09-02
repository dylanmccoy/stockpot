# 04: Auth & login (vs MSW)

**What to build:** Logging in and out, session persistence, and automatic recovery from an expired session — built against mocked auth endpoints. After this ticket a user can log in, stay logged in across a tab reload, get bounced to login on any 401 and returned to where they were, and log out; a developer can reach a registration form when a build flag is set.

**Blocked by:** 02, 03.

**Status:** ready-for-agent

- [ ] Auth provider: token in `localStorage` under `recipe.token`; `login` / `logout`; current user hydrated via `GET /api/auth/me` on load; query cache dropped on `401`.
- [ ] HTTP client `401` interceptor: clear token, drop the query cache, redirect to `/login?next=<attempted path>`.
- [ ] Login page: username + password; failed login shows an inline "invalid username or password" message (not a toast); on success redirect to the `next` param or `/`.
- [ ] Registration form built only when `VITE_ENABLE_REGISTER` is set (`ImportMetaEnv` typed); default bundle has no sign-up UI. When present, it surfaces the specific backend rejection (registration disabled / invalid code / username taken) inline. This ticket owns only the frontend flag; the backend `RECIPE_ALLOW_REGISTRATION` flag is out of scope.
- [ ] Flow test (vs MSW): login success → `next` redirect; login `401` → inline message; each of the 5 `get_current_user` `401` shapes → redirect to login; logout clears token + cache; an expired token present on load → logged-out state.

**Refs:** `docs/frontend/spec.md` §4, §10.1, §6 (401/403 rows); plan Phase 2.
