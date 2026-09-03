# 19b: Hardening — accessibility sweep + loading/empty/error states + DoD

**What to build:** A cross-screen consistency pass: an accessibility sweep across all nine screens, consistent loading / empty / error / not-found states everywhere, a final types re-diff, and the definition-of-done checklist.

**Blocked by:** 14, 15, 16, 17, 18.

**Status:** ready-for-agent

**Files:** cross-screen edits under `frontend/src/pages/*`, `frontend/src/components/*`, `frontend/src/styles/*`; `frontend/src/types.ts` re-diff; `docs/frontend/spec.md` §12 checklist.

**Spec:** `docs/frontend/spec.md` §9 (accessibility bar), §3 "Loading / empty / error conventions", §12 (definition of done); `docs/spec.md` §5 (types re-diff). Read only these sections.

**Tests:** `cd frontend && npm run test:run`, then `npm run test:e2e` (visual / a11y).

- [ ] Accessibility sweep across all nine screens: keyboard traversal, focus moved on route change, `aria-live` on toasts, contrast in both themes, no status conveyed by color alone, reduced-motion honored for spinners and transitions.
- [ ] Loading (skeleton/spinner with nav still usable), empty, error-with-retry, and in-app not-found states are present and consistent on every screen.
- [ ] types module re-diffed against `docs/spec.md` §5 after all Phase 2–6 integration churn.
- [ ] `docs/frontend/spec.md` §12 definition-of-done checklist complete except deployment docs.

**Refs:** `docs/frontend/spec.md` §9, §12; plan Phase 7. Split from ticket 19.
