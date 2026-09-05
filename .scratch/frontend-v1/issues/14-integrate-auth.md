# 14: Integrate auth (real backend)

**What to build:** Switch the auth screen from mocked endpoints to the real backend and confirm the session lifecycle works end to end against it.

**Blocked by:** 04. External gate: backend Phase 2 (auth + app factory) merged.

**Status:** done

- [ ] Login, logout, and `GET /api/auth/me` run against the real backend via the dev proxy.
- [ ] The bearer header format, token field name, and error body shapes match what the client and `parseApiError` expect; any MSW-vs-reality gap is fixed in the handlers and the client.
- [ ] The auth flow tests from ticket 4 pass against the real backend: login success → `next`; login `401` inline; the 5 × `401` shapes → redirect; logout clears.
- [ ] With `VITE_ENABLE_REGISTER` unset there is no sign-up UI; with it set against a backend that has registration disabled, the rejection surfaces inline.
- [ ] Phase 2 gate (plan) closed.

**Refs:** plan Phase 2 gate; `docs/frontend/spec.md` §4, §6.
