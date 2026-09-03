# 11a: Made-history — shared accordion + per-recipe panel (vs MSW)

**What to build:** The reusable cook-log row with its deduction detail, and the per-recipe history panel that uses it inside the recipe detail screen. After this ticket a user opening `/recipes/:id` sees how many times that recipe was made and when, and can expand any cook to its per-ingredient deduction detail.

**Blocked by:** 07, 10.

**Status:** ready-for-agent

**Files:** create `frontend/src/components/CookLogRow.tsx` (+ `.module.css`, `.test.tsx`), `frontend/src/components/DeductionDetail.tsx`; edit `frontend/src/components/index.ts`, `frontend/src/pages/RecipeDetail.tsx`, `frontend/src/api/cookLogs.ts`.

**Spec:** `docs/frontend/spec.md` §10.8 (shared cook-log row, five reason chips, per-recipe panel), §5 "Cook + history" (`CookLogRead`/`CookDeductionRead`). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/components/CookLogRow.test.tsx src/pages/RecipeDetail.test.tsx`.

- [ ] A shared `CookLogRow` + `DeductionDetail` accordion: collapsed shows date, who cooked it, the multiplier, and whether stock was deducted; expanded shows a per-ingredient table (requested, deducted, before, after) with a plain-language reason chip per ingredient covering all five reasons, including the amber "check what you have".
- [ ] A cook logged without deduction shows "logged — stock not changed" with no detail table.
- [ ] The per-recipe panel in `/recipes/:id` lists every cook of that recipe, newest first, unpaginated, with no recipe-title column, filling the placeholder from ticket 07. Query key `["recipe-cook-logs", id]`.
- [ ] Flow test (vs MSW): the panel lists cooks from `["recipe-cook-logs", id]`; expanding a row with one of each of the five reasons renders each chip; a no-deduction row shows the "stock not changed" line and no table.

**Refs:** `docs/frontend/spec.md` §10.8; plan Phase 5. Split from ticket 11.
