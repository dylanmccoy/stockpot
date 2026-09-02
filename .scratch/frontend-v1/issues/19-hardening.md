# 19: Hardening

**What to build:** A cross-screen quality pass — every catalogued error exercised, an accessibility sweep across all nine screens, and consistent loading/empty/error states everywhere.

**Blocked by:** 14, 15, 16, 17, 18.

**Status:** ready-for-agent

- [ ] Every `docs/frontend/spec.md` §6 error-catalog row is exercised by a test: an MSW error handler drives it and the asserted surface (toast / inline-field / inline-form / redirect) is checked.
- [ ] Accessibility sweep across all nine screens: keyboard traversal, focus moved on route change, `aria-live` on toasts, contrast in both themes, no status conveyed by color alone, reduced-motion honored for spinners and transitions.
- [ ] Loading (skeleton/spinner with nav still usable), empty, error-with-retry, and in-app not-found states are present and consistent on every screen.
- [ ] types module re-diffed against `docs/spec.md` §5 after all Phase 2–6 integration churn.
- [ ] React Query defaults (stale time, retry, refetch-on-focus) reviewed for the store-walk case, with a visible "reconnecting" hint and no offline machinery.
- [ ] `docs/frontend/spec.md` §12 definition-of-done checklist complete except deployment docs.

**Refs:** `docs/frontend/spec.md` §6, §9, §12; plan Phase 7.
