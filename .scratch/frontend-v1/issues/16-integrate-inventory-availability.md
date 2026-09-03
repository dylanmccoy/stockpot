# 16: Integrate inventory + availability (real backend)

**What to build:** Wire the inventory screen and the availability table to the real backend, and run the availability adapter diff-review against the merged DTO.

**Blocked by:** 08a, 08b, 09. External gate: backend Phase 4 (inventory + availability) merged.

**Status:** in-review

**Files:** edit `frontend/src/api/inventory.ts`, `frontend/src/api/recipes.ts` (availability), `frontend/src/types.ts`, `docs/frontend/spec.md` §5. External gate: backend Phase 4 merged.

**Spec:** `docs/spec.md` §5.3 (availability) + §5.5 (inventory) as merged — re-diff; `docs/frontend/spec.md` §5, §10.9, §10.4, §7.4. Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/Inventory.test.tsx src/pages/RecipeDetail.test.tsx`, then full `npm run test:run`.

- [x] Inventory CRUD and `GET /api/recipes/{id}/availability` run against the real backend. — verified live against a locally-booted BE Phase 4 (`recipes` POST, `inventory` POST/PATCH/GET, `availability?multiplier=`).
- [x] Availability adapter diff-reviewed against the merged Phase 4 DTO shape (`group_*` fields, status enum values, `nettable`); any change absorbed in the one adapter. — DTO drift found: `AvailabilityLine` gained `ingredient_id: number`; `need_unit` tightened `string | null` → `string`. Both absorbed in `types.ts` + `docs/frontend/spec.md` §5. `api/recipes.ts` `availability()` needs no transform — field names already align, so it stays a typed passthrough.
- [x] The four PATCH-rule rejections and the valid `{ quantity, unit }` update behave the same against the real backend as against MSW; the `match_name` `409` collision surfaces inline. — verified live: `422 "unit is required when setting quantity"`, `422 "unit changes the bucket; remove and re-add"`, `422 "match_name cannot be null"`, `422 "match_name normalizes to empty"`, valid `{quantity:0.5,unit:"kg"}` → `quantity_base 500`, and `409 "match_name already in use for this bucket"` — all match the constants in `pages/Inventory.tsx`.
- [x] The availability header banner and per-line statuses render correctly from real data, including a real `have_uncertain` line as amber with no number. — status enum + line shape verified live; banner / per-status / `have_uncertain` amber-no-number rendering is covered by `RecipeDetail.test.tsx` (fixtures re-diffed to the real DTO, incl. `ingredient_id`, to_taste `need_unit`, `nettable` per §5.3 table).
- [x] types module + `docs/frontend/spec.md` §5 re-diffed for §5.3 and §5.5. — §5.5 Inventory shapes (`InventoryItemCreate/Update/Read`) already match the merged backend; only §5.3 drifted (see above). Header comment in `types.ts` dated.
- [x] Phase 4 gate (plan) closed. — `docs/frontend/plan.md` Phase 4 checkboxes ticked, Exit note + status table updated.

**Refs:** plan Phase 4 gate; `docs/frontend/spec.md` §10.9, §10.4, §7.4.

## Comments

- Branch `feat/frontend-v1-16`; worktree `.claude/worktrees/frontend-v1-16`.
- Changed: `frontend/src/types.ts`, `docs/frontend/spec.md` §5, `frontend/src/pages/RecipeDetail.test.tsx` (fixture re-diff), `docs/frontend/plan.md` (Phase 4 gate). `frontend/src/api/inventory.ts` and `frontend/src/api/recipes.ts` unchanged — no adapter transform needed.
- Full frontend suite green (`npm run test:run` — 279 passed), `npm run typecheck`, `npm run lint`, `npm run build` all clean.
