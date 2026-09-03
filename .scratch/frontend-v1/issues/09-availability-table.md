# 09: Availability table (vs MSW)

**What to build:** Showing, inside the recipe detail screen, whether the household can cook a recipe right now at the chosen multiplier. After this ticket a user sees a per-ingredient availability table scaled by the multiplier, with a status per line and a header banner summarizing the answer.

**Blocked by:** 07.

**Status:** ready-for-agent

**Files:** edit `frontend/src/pages/RecipeDetail.tsx`, `frontend/src/pages/RecipeDetail.test.tsx`, `frontend/src/api/recipes.ts` (availability adapter). Built against the spec DTO — **not** wired to real calls (ticket 16).

**Spec:** `docs/frontend/spec.md` §10.4 (availability table), §7.4 ("uncertain" language), §5 "Availability" (`AvailabilityLineDTO`). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/RecipeDetail.test.tsx`.

- [ ] The availability table renders inside `/recipes/:id` against current inventory, scaled by the multiplier control.
- [ ] Each ingredient is marked: have it, short by X, check what you have, missing, or to taste.
- [ ] A "check what you have" line renders amber with an explanation that stock is held in an incomparable unit, and shows **no** shortfall number.
- [ ] Ingredients sharing a match name and unit are grouped into one row (dedupe by `group_key`, or render per member line consistently).
- [ ] A header banner states whether everything is available or how many items are missing.
- [ ] The availability call sits behind the recipes resource adapter (R-2 containment); it is built against the spec DTO and **not** wired to real calls here (that is ticket 16).

**Refs:** `docs/frontend/spec.md` §10.4 (availability), §7.4; plan Phase 4.
