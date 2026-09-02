# 19: Hardening — SPLIT

**Status:** split — do not implement this ticket directly.

Split into vertical slices:

- **19a — Error-catalog coverage + React Query defaults.** Every `docs/frontend/spec.md` §6 row driven by an MSW error handler with the asserted surface checked; RQ retry/stale/refetch reviewed for the store-walk case + "reconnecting" hint. Blocked by 14, 15, 16, 17, 18.
- **19b — Accessibility sweep + loading/empty/error states + DoD.** A11y across all nine screens; consistent loading / empty / error-with-retry / in-app not-found states; final types re-diff; §12 definition-of-done checklist (minus deployment docs). Blocked by 14, 15, 16, 17, 18.

**Downstream edges retargeted:** 20 → 19a, 19b.

**Refs:** `docs/frontend/spec.md` §6, §9, §12; plan Phase 7.
