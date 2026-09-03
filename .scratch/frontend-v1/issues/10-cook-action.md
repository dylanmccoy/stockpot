# 10: Cook action (vs MSW)

**What to build:** Recording that a recipe was made, optionally deducting the scaled amounts from inventory. After this ticket a user can mark a recipe cooked at the current multiplier with a deduct toggle, and the availability and inventory views refresh to reflect the new stock; there is no undo.

**Blocked by:** 09, 08a.

**Status:** ready-for-agent

**Files:** edit `frontend/src/pages/RecipeDetail.tsx`, `frontend/src/pages/RecipeDetail.test.tsx`, `frontend/src/api/recipes.ts` (cook adapter). Built against the spec DTO — **not** wired to real calls (ticket 17).

**Spec:** `docs/frontend/spec.md` §10.4 (cook action), §5 "Cook + history" (`/cook` body + `CookLogRead`). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/RecipeDetail.test.tsx`.

- [ ] `/recipes/:id` has a "mark as cooked" button and a "deduct from inventory" toggle (on by default) next to it.
- [ ] Cooking posts at the current multiplier; a double batch deducts twice the stock.
- [ ] On success, the availability table, inventory, and cook-log views are invalidated and refetch.
- [ ] On a `409` stock-collision, a clear retry message is shown and the data refetches.
- [ ] No "undo cook" affordance anywhere.
- [ ] The cook call sits behind the recipes resource adapter (R-2); built against the spec DTO, **not** wired to real calls here (that is ticket 17).

**Refs:** `docs/frontend/spec.md` §10.4 (cook action); plan Phase 5.
