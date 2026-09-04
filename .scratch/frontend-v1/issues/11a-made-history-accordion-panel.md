# 11a: Made-history — shared accordion + per-recipe panel (vs MSW)

**What to build:** The reusable cook-log row with its deduction detail, and the per-recipe history panel that uses it inside the recipe detail screen. After this ticket a user opening `/recipes/:id` sees how many times that recipe was made and when, and can expand any cook to its per-ingredient deduction detail.

**Blocked by:** 07, 10.

**Status:** in-review

**Files:** create `frontend/src/components/CookLogRow.tsx` (+ `.module.css`, `.test.tsx`), `frontend/src/components/DeductionDetail.tsx`; edit `frontend/src/components/index.ts`, `frontend/src/pages/RecipeDetail.tsx`, `frontend/src/api/cookLogs.ts`.

**Spec:** `docs/frontend/spec.md` §10.8 (shared cook-log row, five reason chips, per-recipe panel), §5 "Cook + history" (`CookLogRead`/`CookDeductionRead`). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/components/CookLogRow.test.tsx src/pages/RecipeDetail.test.tsx`.

- [x] A shared `CookLogRow` + `DeductionDetail` accordion: collapsed shows date, who cooked it, the multiplier, and whether stock was deducted; expanded shows a per-ingredient table (requested, deducted, before, after) with a plain-language reason chip per ingredient covering all five reasons, including the amber "check what you have".
- [x] A cook logged without deduction shows "logged — stock not changed" with no detail table.
- [x] The per-recipe panel in `/recipes/:id` lists every cook of that recipe, newest first, unpaginated, with no recipe-title column, filling the placeholder from ticket 07. Query key `["recipe-cook-logs", id]`.
- [x] Flow test (vs MSW): the panel lists cooks from `["recipe-cook-logs", id]`; expanding a row with one of each of the five reasons renders each chip; a no-deduction row shows the "stock not changed" line and no table.

**Refs:** `docs/frontend/spec.md` §10.8; plan Phase 5. Split from ticket 11.

## Comments

- Branch `feat/frontend-v1-11a`; worktree `.claude/worktrees/frontend-v1-11a`.
- API: added `cookLogsApi.byRecipe`; removed the now-redundant unused
  `recipesApi.cookLogs` (one adapter home per concern — R-2).
- Deviations from spec §10.8, deliberate:
  - Panel header uses `formatDateTime(latest)` not `formatRelative` — §7.2 marks
    `formatRelative` optional and it is unimplemented.
  - `ok` deductions get a quiet neutral "deducted" chip rather than "none", so
    every ingredient row carries a chip (ticket AC 1 + flow test require all
    five reasons to render one).
  - Collapsed summary adds "N to check" for `have uncertain` rows, parallel to
    the spec's "ran out" / "not tracked" examples.
  - `CookLogRow` carries an unused-in-11a `showRecipeTitle` prop + deleted-recipe
    marker: it is the shared row for the global `/history` feed (ticket 11b),
    spec §10.8 "one shared `CookLogRow`".
- `/code-review` findings actioned: dropped `deductionSummary` from the
  component barrel, renamed `.availError` → `.panelError`, renamed `span()` →
  `rangeLabel()`, added an explicit "stock updated" deduct token, moved the
  cook-log fixture builders to `test/handlers.ts` (`makeCookLog` /
  `makeDeduction`).
