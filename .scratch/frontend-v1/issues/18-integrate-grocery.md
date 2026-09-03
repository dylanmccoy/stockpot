# 18: Integrate grocery (real backend)

**What to build:** Wire the full grocery flow to the real backend and run the grocery adapter diff-review against the merged DTO.

**Blocked by:** 12a, 12b, 13a, 13b, 13c. External gate: backend Phase 6 (grocery lists) merged.

**Status:** ready-for-agent

**Files:** edit `frontend/src/api/grocery.ts`, `frontend/src/types.ts`, `docs/frontend/spec.md` §5. External gate: backend Phase 6 merged.

**Spec:** `docs/spec.md` §5.6 (grocery as merged — re-diff: line classification, `nettable`, `applied_*`, list status); `docs/frontend/spec.md` §5, §10.5–§10.7. Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/GroceryLists.test.tsx src/pages/GroceryListDetail.test.tsx src/pages/RecipeList.test.tsx`, then full `npm run test:run`.

- [ ] Grocery create, list index, list detail, line add/edit, submit, and archive run against the real backend.
- [ ] Grocery adapter diff-reviewed against the merged Phase 6 DTO (line classification, `nettable`, `applied_*` fields, list status).
- [ ] The check→submit flow test passes against the real backend: check two lines → submit → lines frozen and inventory invalidated; PATCH a frozen line → `409` copy; edit a generated line → reclassified to manual.
- [ ] `POST /api/grocery` with a missing `recipe_id` returns `422` and the create dialog's recovery path works against real data.
- [ ] Optimistic check/uncheck rolls back correctly on a real rejection.
- [ ] types module + `docs/frontend/spec.md` §5 re-diffed for §5.6.
- [ ] Phase 6 gate (plan) closed.

**Refs:** plan Phase 6 gate; `docs/frontend/spec.md` §10.5–§10.7.
