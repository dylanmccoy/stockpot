# 18: Integrate grocery (real backend)

**What to build:** Wire the full grocery flow to the real backend and run the grocery adapter diff-review against the merged DTO.

**Blocked by:** 12a, 12b, 13a, 13b, 13c. External gate: backend Phase 6 (grocery lists) merged.

**Status:** done

**Files:** edit `frontend/src/api/grocery.ts`, `frontend/src/types.ts`, `docs/frontend/spec.md` §5. External gate: backend Phase 6 merged.

**Spec:** `docs/spec.md` §5.6 (grocery as merged — re-diff: line classification, `nettable`, `applied_*`, list status); `docs/frontend/spec.md` §5, §10.5–§10.7. Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/GroceryLists.test.tsx src/pages/GroceryListDetail.test.tsx src/pages/RecipeList.test.tsx`, then full `npm run test:run`.

- [x] Grocery create, list index, list detail, line add/edit, submit, and archive run against the real backend.
- [x] Grocery adapter diff-reviewed against the merged Phase 6 DTO (line classification, `nettable`, `applied_*` fields, list status).
- [x] The check→submit flow test passes against the real backend: check two lines → submit → lines frozen and inventory invalidated; PATCH a frozen line → `409` copy; edit a generated line → reclassified to manual.
- [x] `POST /api/grocery` with a missing `recipe_id` returns `422` and the create dialog's recovery path works against real data.
- [x] Optimistic check/uncheck rolls back correctly on a real rejection.
- [x] types module + `docs/frontend/spec.md` §5 re-diffed for §5.6.
- [x] Phase 6 gate (plan) closed.

**Refs:** plan Phase 6 gate; `docs/frontend/spec.md` §10.5–§10.7.

## Comments

Branch `feat/frontend-v1-18` in worktree
`.claude/worktrees/frontend-v1-18`.

Live re-diff against a booted BE Phase 6 (real HTTP, not MSW) found one real
drift: `GroceryListItemIn.quantity`/`.unit` were `?:` (omittable) in
`types.ts`, but the backend schema requires both keys present (nullable, no
default) — an amount-less manual-line add omitted them and 422'd. Fixed
`types.ts`, `docs/frontend/spec.md` §5, `buildAddLine` in
`GroceryListDetail.tsx`, and the corresponding unit test. Everything else
(`GroceryListCreate`, `GroceryListItemUpdate`, `GroceryListItemRead`,
`GroceryListRead`) matched field-for-field — no other code changes.

Live-drove: create + `422` missing `recipe_id`; check two lines → submit →
both frozen with `applied_*` set, `GET /inventory` shows both; `PATCH`/`DELETE`
on a frozen line → `409`; non-atomic `{quantity}`-only PATCH → `422` (N6);
edit an unfrozen generated line → reclassified `manual`/`nettable:true`;
archive → `409` on re-archive/PATCH/submit/item-POST of an archived list;
`DELETE` on any status.

Full suite green: `npm run test:run` (349 passed), typecheck, lint, build.
