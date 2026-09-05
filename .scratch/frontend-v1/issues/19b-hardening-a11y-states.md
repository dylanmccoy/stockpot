# 19b: Hardening — accessibility sweep + loading/empty/error states + DoD

**What to build:** A cross-screen consistency pass: an accessibility sweep across all nine screens, consistent loading / empty / error / not-found states everywhere, a final types re-diff, and the definition-of-done checklist.

**Blocked by:** 14, 15, 16, 17, 18.

**Status:** in-review

**Files:** cross-screen edits under `frontend/src/pages/*`, `frontend/src/components/*`, `frontend/src/styles/*`; `frontend/src/types.ts` re-diff; `docs/frontend/spec.md` §12 checklist.

**Spec:** `docs/frontend/spec.md` §9 (accessibility bar), §3 "Loading / empty / error conventions", §12 (definition of done); `docs/spec.md` §5 (types re-diff). Read only these sections.

**Tests:** `cd frontend && npm run test:run`, then `npm run test:e2e` (visual / a11y).

- [x] Accessibility sweep across all nine screens: keyboard traversal, focus moved on route change, `aria-live` on toasts, contrast in both themes, no status conveyed by color alone, reduced-motion honored for spinners and transitions. — audited every screen + shared primitive (`AppShell`, `Dialog`, `Field`, `Toast`, `Badge`, `Stepper`, `DataTable`, `CookLogRow`); all clear the §9 bar already (baked in from Phase 1 per Q25). No gap found, no code change needed.
- [x] Loading (skeleton/spinner with nav still usable), empty, error-with-retry, and in-app not-found states are present and consistent on every screen. — `AppShell`'s nav/header sit outside every screen's content region, so it's always interactive during a screen's loading state; all nine screens follow the §3 table (`role="status"` loading, centered empty + primary action, `role="alert"` + Retry on query error, in-content not-found panel on `/recipes/:id` and `/groceries/:id`). No gap found.
- [x] types module re-diffed against `docs/spec.md` §5 after all Phase 2–6 integration churn. — full-file re-diff; only §5.1 (auth) had never gotten its own dated line despite shipping in ticket 14 — checked now, no drift. Dated note added to `types.ts`.
- [x] `docs/frontend/spec.md` §12 definition-of-done checklist complete except deployment docs. — verified each bullet: `npm run lint && npm run test:run && npm run build` green (363 tests, 35 files); `npm run test:e2e` green; flow-test coverage for Login/RecipeForm/Inventory-PATCH/Grocery-check→submit confirmed; no signup UI reachable in the default bundle (`VITE_ENABLE_REGISTER` unset — no `/register` route, `Login` gates `RegisterForm` behind the flag). LAN deployment notes (Phase 8) remain outstanding as expected, blocked on backend Phase 7.

**Refs:** `docs/frontend/spec.md` §9, §12; plan Phase 7. Split from ticket 19.

## Comments

- Branch `feat/frontend-v1-19b`; worktree `.claude/worktrees/frontend-v1-19b`.
- This was a verification sweep, not new feature code: tickets 14–18 and the
  Phase 1 component system (Q25) had already built every screen to the §9 bar
  and the §3 state conventions. No a11y or loading/empty/error defect found
  anywhere in the nine screens or the shared primitives — nothing to fix.
- Real change: `frontend/src/types.ts` (closed the one un-dated re-diff gap,
  §5.1 auth — no drift), `docs/frontend/plan.md` (Phase 7 checklist ticked,
  status table row, Exit note — closes the phase gate that 19a left open).
- Full frontend suite green: `npm run test:run` (363 passed, 35 files),
  `npm run typecheck`, `npm run lint`, `npm run build`, `npm run test:e2e`
  (2 passed, light + dark) all clean.
