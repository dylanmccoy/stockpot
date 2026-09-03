# 09: Availability table (vs MSW)

**What to build:** Showing, inside the recipe detail screen, whether the household can cook a recipe right now at the chosen multiplier. After this ticket a user sees a per-ingredient availability table scaled by the multiplier, with a status per line and a header banner summarizing the answer.

**Blocked by:** 07.

**Status:** in-review

**Files:** edit `frontend/src/pages/RecipeDetail.tsx`, `frontend/src/pages/RecipeDetail.test.tsx`, `frontend/src/api/recipes.ts` (availability adapter). Built against the spec DTO — **not** wired to real calls (ticket 16).

**Spec:** `docs/frontend/spec.md` §10.4 (availability table), §7.4 ("uncertain" language), §5 "Availability" (`AvailabilityLineDTO`). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/RecipeDetail.test.tsx`.

- [x] The availability table renders inside `/recipes/:id` against current inventory, scaled by the multiplier control.
- [x] Each ingredient is marked: have it, short by X, check what you have, missing, or to taste.
- [x] A "check what you have" line renders amber with an explanation that stock is held in an incomparable unit, and shows **no** shortfall number.
- [x] Ingredients sharing a match name and unit are grouped into one row (dedupe by `group_key`, or render per member line consistently).
- [x] A header banner states whether everything is available or how many items are missing.
- [x] The availability call sits behind the recipes resource adapter (R-2 containment); it is built against the spec DTO and **not** wired to real calls here (that is ticket 16).

**Refs:** `docs/frontend/spec.md` §10.4 (availability), §7.4; plan Phase 4.

## Comments

- Branch `feat/frontend-v1-09`, worktree `.claude/worktrees/frontend-v1-09`.
- `api/recipes.ts` untouched: `recipesApi.availability` already existed from an
  earlier phase and matches the §5 DTO, so no adapter edit was needed.
- Implementation in `RecipeDetail.tsx`: `AvailabilityPanel` runs
  `["availability", id, multiplier]` through the adapter (`keepPreviousData` so
  the table doesn't flash on a multiplier change). Lines are collapsed to one
  row per `group_key` (`groupAvailabilityLines`), rendered in a `DataTable` with
  a status `Badge` per §7.4. Each badge carries a text label + a non-color glyph
  (§9); `have_uncertain` adds the cans-vs-grams subtext and never a number.
- Banner: trusts server `all_available` for "You have everything"; otherwise
  tallies distinct short/missing groups → "Missing N items". `have_uncertain` is
  **excluded** from that count (§7.4 — the household may have it); a report whose
  only gaps are `have_uncertain` shows "Check what you have" instead.
- `/implement` two-axis review actioned: consolidated three parallel status maps
  into one `STATUS_META` descriptor; extracted `withUnitWord` (shared by
  `amountLabel` / `scaledQuantityLabel`); added `aria-live="polite"` to the
  banner; fixed the banner counting `have_uncertain` as "missing".
- Deliberately kept (flagged as possible scope creep): the availability
  error/Retry state (§170 global loading/empty/error convention) and status
  glyphs (§9). The `Need` column still shows the scaled requirement for a
  `have_uncertain` row — §7.4 and the acceptance criterion both scope the ban to
  the *shortfall* number, and the column header labels it as the requirement.
- Tests: `RecipeDetail.test.tsx` — 22 cases (pure `groupAvailabilityLines` /
  `amountLabel` + screen). Full frontend suite 279 pass; typecheck + lint clean.
