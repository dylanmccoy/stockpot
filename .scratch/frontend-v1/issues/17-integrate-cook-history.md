# 17: Integrate cook + history (real backend)

**What to build:** Wire the cook action and both history views to the real backend, run the cook adapter diff-review, and confirm the deduction accordion against real deduction data.

**Blocked by:** 10, 11a, 11b. External gate: backend Phase 5 (cooking + history) merged.

**Status:** in-review

**Files:** edit `frontend/src/api/cookLogs.ts`, `frontend/src/api/recipes.ts` (cook), `frontend/src/types.ts`, `docs/frontend/spec.md` §5. External gate: backend Phase 5 merged.

**Spec:** `docs/spec.md` §5.4 (cook + history as merged — re-diff; null rules); `docs/frontend/spec.md` §5, §10.4, §10.8. Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/RecipeDetail.test.tsx src/pages/History.test.tsx`, then full `npm run test:run`.

- [x] The cook action, the per-recipe history panel, and `/history` run against the real backend. — `api/cookLogs.ts` / `api/recipes.ts` cook adapter were already plain `client` calls against `/api/recipes/{id}/cook`, `/api/recipes/{id}/cook-logs`, `/api/cook-logs` (no MSW-only shim); verified live against a locally-booted BE Phase 5.
- [x] Cook adapter diff-reviewed against the merged Phase 5 deduction DTO. — no drift: `CookRequest`, `CookDeductionRead`, `CookLogRead` in `types.ts` match `backend/app/schemas/cook_logs.py` field-for-field. Confirmed live: one real `POST /recipes/{id}/cook` against a recipe/inventory set up to hit all five reasons returned exactly the null-per-branch shape the frontend expects.
- [x] Posting a cook invalidates and refetches availability, inventory, and cook-logs against the real backend; a real `409` stock-collision shows the retry copy and refetches. — invalidation wiring already in `CookPanel` (ticket 10); the 409 path is exercised by `RecipeDetail.test.tsx` ("on a 409 stock collision, toasts a retry message and refetches"); error *shape* (`409` via the global IntegrityError/lock-timeout handler) matches `lib/apiError.ts` — no adapter change needed.
- [x] The `DeductionDetail` accordion renders all five reason branches from real cook logs, with nulls only where `docs/spec.md` §5.4 permits. — verified live: `ok`, `clamped to 0`, `to taste`, `not in inventory`, `have uncertain (incompatible unit)` all produced by one real cook and rendered correctly (component already implements all five chips, ticket 11a).
- [x] A deleted recipe still shows its title as plain text in `/history` rows. — verified live: `DELETE /recipes/{id}` then `GET /cook-logs` returns `recipe_id: null` with the `recipe_title` snapshot intact; `CookLogRow` already renders that as plain text + "(recipe deleted)" (ticket 11b).
- [x] types module + `docs/frontend/spec.md` §5 re-diffed for §5.4. — `types.ts` header dated for §5.4; `docs/frontend/spec.md` §5 cook section already matched the merged backend, no text changes needed.
- [x] Phase 5 gate (plan) closed. — `docs/frontend/plan.md` Phase 5 checkboxes ticked, Exit note + status table updated.

**Refs:** plan Phase 5 gate; `docs/frontend/spec.md` §10.4, §10.8.

## Comments

- Branch `feat/frontend-v1-17`; worktree `.claude/worktrees/frontend-v1-17`.
- Changed: `frontend/src/types.ts` (dated re-diff note only), `docs/frontend/plan.md`
  (Phase 5 gate + status table). `frontend/src/api/cookLogs.ts`,
  `frontend/src/api/recipes.ts`, and `docs/frontend/spec.md` unchanged — no
  adapter transform or spec text needed, no DTO drift found.
- Tickets 10 / 11a / 11b were already merged straight against the real endpoint
  shapes (not an MSW-only mock), so this ticket's work was verification, not new
  code: a locally-booted BE Phase 5 backend, a recipe + inventory set built to
  hit all five `CookDeductionReason` branches in one `POST /cook`, and a recipe
  delete to check the `recipe_id: null` / `recipe_title` snapshot path.
- Full frontend suite green (`npm run test:run` — 349 passed), `npm run
  typecheck`, `npm run lint` all clean.
