# 13b: Grocery list — add + edit lines (vs MSW)

**What to build:** Adjusting a grocery list in the store: adding lines for things not derived from a recipe, and correcting the solver's generated lines. After this ticket a user can add a manual line and edit a generated line's item, quantity, or unit, with a quiet note when an edit reclassifies a generated line to manual.

**Blocked by:** 13a.

**Status:** ready-for-agent

**Files:** edit `frontend/src/pages/GroceryListDetail.tsx`, `frontend/src/pages/GroceryListDetail.test.tsx`, `frontend/src/api/grocery.ts`.

**Spec:** `docs/frontend/spec.md` §10.7 (add manual line, edit generated line — `quantity`+`unit` sent together, reclassify-to-manual note), §5 "Grocery" (`POST`/`PATCH` `/api/grocery/{id}/items`). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/GroceryListDetail.test.tsx`.

- [ ] Add a manual line with an item and optional quantity/unit.
- [ ] Edit a generated line's item, quantity, or unit, sending quantity and unit together.
- [ ] A quiet note explains when editing a generated line reclassifies it to manual (no longer netted against stock).
- [ ] Flow test (vs MSW): adding a manual line POSTs the right body and it appears in the manual group; editing a generated line's quantity sends `{ quantity, unit }` together and shows the reclassify note.

**Refs:** `docs/frontend/spec.md` §10.7; plan Phase 6. Split from ticket 13.
