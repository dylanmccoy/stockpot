# 06c: Recipe form — edit / PUT full-replace (vs MSW)

**What to build:** Editing an existing recipe through the same form, pre-filled, with a save that fully replaces the recipe so removed rows actually disappear. After this ticket a user can open `/recipes/:id/edit`, see the form populated from the current recipe, change or delete rows, and save a PUT full-replace that drops the removed rows.

**Blocked by:** 06a.

**Status:** done

**Files:** edit `frontend/src/pages/RecipeForm.tsx`, `frontend/src/pages/RecipeForm.test.tsx`, `frontend/src/api/recipes.ts` (PUT full-replace adapter).

**Spec:** `docs/frontend/spec.md` §10.3 (RecipeForm edit / PUT full-replace), §5 "Recipes" (PUT shape). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/RecipeForm.test.tsx`.

- [ ] `/recipes/:id/edit` fetches the recipe and pre-fills every field, step, and ingredient row.
- [ ] Save uses `PUT` full-replace; removed steps and ingredient rows are absent from the body and gone after refetch.
- [ ] The ingredient-row `id` churn on `PUT` does not break the table (row identity is not keyed on the server `id` across an edit).
- [ ] The mixed string/object `ingredients` rule from 06b still holds on edit: untouched pasted rows stay strings, edited rows become objects.
- [ ] Flow test (vs MSW): open `/recipes/1/edit` → fields pre-filled; delete a row → `PUT` body omits it → refetch shows it gone; re-edit the same recipe → no stale-key crash.

**Refs:** `docs/frontend/spec.md` §10.3; plan Phase 3. Split from ticket 06.
