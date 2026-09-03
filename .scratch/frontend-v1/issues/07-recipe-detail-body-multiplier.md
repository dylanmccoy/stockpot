# 07: Recipe detail body + multiplier (vs MSW)

**What to build:** Viewing a recipe and scaling it. After this ticket a user can open `/recipes/:id`, read the ingredients with human-formatted quantities and the steps/notes/meta, scale the recipe with a multiplier control that resets each visit, follow the source link, and delete the recipe with a confirmation.

**Blocked by:** 05a, 03.

**Status:** ready-for-agent

**Files:** edit `frontend/src/pages/RecipeDetail.tsx`, `frontend/src/api/recipes.ts`; create `frontend/src/pages/RecipeDetail.module.css`, `frontend/src/pages/RecipeDetail.test.tsx`. Use `frontend/src/lib/format.ts` and `frontend/src/components/Stepper.tsx` as-is.

**Spec:** `docs/frontend/spec.md` §10.4 (RecipeDetail body), §7.2 (`format` — `formatQuantity`). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/RecipeDetail.test.tsx`.

- [ ] `/recipes/:id` shows ingredients in order with `formatQuantity` output (e.g. "1½ cups"); a raw converted float is never shown unformatted.
- [ ] Shows steps, notes, cuisine, servings, prep/cook time. `source_url` as an "open link" when a valid URL.
- [ ] Delete action → confirmation dialog → on success navigate to `/`.
- [ ] Multiplier: one `Stepper` with presets ½, 1, 2, 3 and a free numeric input (`> 0`). Changing it rescales the displayed ingredient quantities. Resets to 1 on every visit to the screen.
- [ ] A per-recipe made-history panel placeholder is present but empty (filled in ticket 11).
- [ ] Not-found: hitting the URL for a missing recipe shows an in-content "not found" panel with a link back to the list.

**Refs:** `docs/frontend/spec.md` §10.4 (body), §7.2; plan Phase 3.
