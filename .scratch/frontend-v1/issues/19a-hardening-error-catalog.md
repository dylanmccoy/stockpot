# 19a: Hardening — error-catalog coverage + React Query defaults

**What to build:** Every catalogued error exercised by a test, and the query-client defaults reviewed for the store-walk case. After this ticket each `docs/frontend/spec.md` §6 row has a test that drives it through an MSW error handler and asserts the surface it produces, and TanStack Query's retry/stale/refetch behavior is deliberate with a visible "reconnecting" hint.

**Blocked by:** 14, 15, 16, 17, 18.

**Status:** ready-for-agent

- [ ] Every `docs/frontend/spec.md` §6 error-catalog row is exercised by a test: an MSW error handler drives it and the asserted surface (toast / inline-field / inline-form / redirect) is checked.
- [ ] React Query defaults (stale time, retry, refetch-on-focus) reviewed for the store-walk case, with a visible "reconnecting" hint and no offline machinery.
- [ ] Any gap found (a row with no surface, or the wrong surface) is fixed in the owning screen or the client.

**Refs:** `docs/frontend/spec.md` §6; plan Phase 7. Split from ticket 19.
