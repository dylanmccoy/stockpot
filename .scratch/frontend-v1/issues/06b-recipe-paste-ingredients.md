# 06b: Recipe form — paste ingredients with preview (vs MSW)

**What to build:** Pasting a block of ingredient lines from a website and fixing the parse before it becomes rows. After this ticket a user editing the ingredient table can paste a multi-line block, see how each line was interpreted (quantity / unit / item / note), confirm to append the parsed rows, and hand-fix any misparse before saving.

**Blocked by:** 06a.

**Status:** done

**Files:** edit `frontend/src/pages/RecipeForm.tsx`, `frontend/src/pages/RecipeForm.module.css`, `frontend/src/pages/RecipeForm.test.tsx`. Use `frontend/src/lib/parseIngredients.ts` as-is (do not edit it or its oracle).

**Spec:** `docs/frontend/spec.md` §7.1 (`parseIngredients` behaviour), §10.3 (RecipeForm). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/RecipeForm.test.tsx`.

- [ ] A "Paste ingredients" action opens an input for a multi-line block and runs `parseIngredients` on it.
- [ ] A parsed-row preview shows quantity / unit / item / note per line; confirm appends those rows to the ingredient table, cancel discards them.
- [ ] After appending, the user can edit any appended row in the normal table before saving.
- [ ] Pasted-untouched rows are sent as strings; hand-entered or edited rows as objects, in one mixed `ingredients` array on save.
- [ ] Flow test (vs MSW): paste a block with a blank line, a bullet marker, and a `For the sauce:` header → preview drops/strips them per the `parseIngredients` oracle; confirm → rows appended; save → `ingredients` array carries string elements for untouched rows and objects for edited ones.

**Refs:** `docs/frontend/spec.md` §7.1, §10.3; plan Phase 3. Split from ticket 06.
