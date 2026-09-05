# 10: Cook action (vs MSW)

**What to build:** Recording that a recipe was made, optionally deducting the scaled amounts from inventory. After this ticket a user can mark a recipe cooked at the current multiplier with a deduct toggle, and the availability and inventory views refresh to reflect the new stock; there is no undo.

**Blocked by:** 09, 08a.

**Status:** done

**Files:** edit `frontend/src/pages/RecipeDetail.tsx`, `frontend/src/pages/RecipeDetail.test.tsx`, `frontend/src/api/recipes.ts` (cook adapter). Built against the spec DTO — **not** wired to real calls (ticket 17).

**Spec:** `docs/frontend/spec.md` §10.4 (cook action), §5 "Cook + history" (`/cook` body + `CookLogRead`). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/RecipeDetail.test.tsx`.

- [x] `/recipes/:id` has a "mark as cooked" button and a "deduct from inventory" toggle (on by default) next to it.
- [x] Cooking posts at the current multiplier; a double batch deducts twice the stock. (FE sends `{ multiplier, deduct }`; the doubling is the backend's.)
- [x] On success, the availability table, inventory, and cook-log views are invalidated and refetch. (Invalidates `["availability", id]`, `["inventory"]`, `["cook-logs"]`, `["recipe-cook-logs", id]`; only the mounted availability observer refetches on this screen.)
- [x] On a `409` stock-collision, a clear retry message is shown and the data refetches.
- [x] No "undo cook" affordance anywhere.
- [x] The cook call sits behind the recipes resource adapter (R-2); built against the spec DTO, **not** wired to real calls here (that is ticket 17). (`recipesApi.cook` already existed unchanged.)

**Refs:** `docs/frontend/spec.md` §10.4 (cook action); plan Phase 5.

## Comments

- Branch `feat/frontend-v1-10`, worktree `.claude/worktrees/frontend-v1-10`.
- Implemented as a `CookPanel` section on `RecipeDetail` (button + deduct checkbox
  + a permanence note). 6 new tests in `RecipeDetail.test.tsx` (28 pass); full FE
  suite 289 pass; typecheck + lint clean.
- `frontend/src/api/recipes.ts` needed no change — the `cook` adapter was already
  present from an earlier ticket.
