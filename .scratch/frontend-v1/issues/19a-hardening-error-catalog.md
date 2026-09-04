# 19a: Hardening — error-catalog coverage + React Query defaults

**What to build:** Every catalogued error exercised by a test, and the query-client defaults reviewed for the store-walk case. After this ticket each `docs/frontend/spec.md` §6 row has a test that drives it through an MSW error handler and asserts the surface it produces, and TanStack Query's retry/stale/refetch behavior is deliberate with a visible "reconnecting" hint.

**Blocked by:** 14, 15, 16, 17, 18.

**Status:** in-review

**Files:** edit `frontend/src/test/errorHandlers.ts`, `frontend/src/test/errorHandlers.test.ts`, `frontend/src/api/client.ts` + `frontend/src/main.tsx` (QueryClient defaults), plus the owning screen for any gap found.

**Spec:** `docs/frontend/spec.md` §6 (error model & catalog — one test per row), §3 "Loading / empty / error conventions". Read only these sections.

**Tests:** `cd frontend && npm run test:run` (cross-screen).

- [x] Every `docs/frontend/spec.md` §6 error-catalog row is exercised by a test: an MSW error handler drives it and the asserted surface (toast / inline-field / inline-form / redirect) is checked.
- [x] React Query defaults (stale time, retry, refetch-on-focus) reviewed for the store-walk case, with a visible "reconnecting" hint and no offline machinery.
- [x] Any gap found (a row with no surface, or the wrong surface) is fixed in the owning screen or the client.

**Refs:** `docs/frontend/spec.md` §6; plan Phase 7. Split from ticket 19.

## Comments

Branch `feat/frontend-v1-19a`, worktree `.claude/worktrees/frontend-v1-19a`.

Audited all 12 §6 catalog rows against the screen test suite: 10 already had
a real MSW-driven surface assertion from tickets 14–18. Closed the two
endpoint-level gaps the catalog's "endpoints" column named but no test hit
directly:

- 409 `"conflict"` on `POST /api/grocery/:id/submit` →
  `pages/GroceryListDetail.test.tsx` ("on a 409 stock collision from submit,
  toasts a retry message and refetches").
- 409 `"conflict"` (generic, not `match_name`) on `PATCH /api/inventory/:id`
  edit → `pages/Inventory.test.tsx` ("on a generic 409 edit conflict, toasts
  + refetches and closes the panel").

Both surfaces were already implemented correctly in the owning screens —
this was test coverage, not a code fix.

React Query defaults: replaced `main.tsx`'s blanket `retry: 1` (retried
every error including 404/422/409, delaying the real surface) with
`app/queryClient.ts` — retry only a transport failure (`ApiError.status ===
0`), exponential backoff capped at 30s, `refetchOnReconnect: true`,
`staleTime: 0` (nothing polls; staying "stale" buys no fewer requests, only
a chance of stale numbers on the store walk), mutations never auto-retry
(no blind double-submit on a `cook`/`submit`/`POST`). Added a "Reconnecting…"
hint in `AppShell` (`app/connectivity.ts`, wraps TanStack Query's own
`onlineManager` — no service worker, no persisted cache).

`errorHandlers.ts` / `errorHandlers.test.ts` and `api/client.ts` (both named
in **Files:** above) needed no changes — every catalog-row handler already
existed and `client.ts` already normalized a transport failure to
`ApiError(0, …)` pre-ticket.

Ran `/code-review` (Standards + Spec axes) against `main`. Standards: clean,
no hard violations. Spec: one finding — `staleTime: 0` had no rationale or
test, so "defaults reviewed" didn't visibly hold for that field; fixed with
a comment + a `queryClient.test.ts` assertion (commit `44e4512`).

`npm run typecheck` / `npm run lint` / `npm run test:run` (363 tests) all
green on the branch.
