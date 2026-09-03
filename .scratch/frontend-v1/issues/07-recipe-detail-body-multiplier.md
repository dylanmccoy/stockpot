# 07: Recipe detail body + multiplier (vs MSW)

**What to build:** Viewing a recipe and scaling it. After this ticket a user can open `/recipes/:id`, read the ingredients with human-formatted quantities and the steps/notes/meta, scale the recipe with a multiplier control that resets each visit, follow the source link, and delete the recipe with a confirmation.

**Blocked by:** 05a, 03.

**Status:** done

**Files:** edit `frontend/src/pages/RecipeDetail.tsx`, `frontend/src/api/recipes.ts`; create `frontend/src/pages/RecipeDetail.module.css`, `frontend/src/pages/RecipeDetail.test.tsx`. Use `frontend/src/lib/format.ts` and `frontend/src/components/Stepper.tsx` as-is.

**Spec:** `docs/frontend/spec.md` §10.4 (RecipeDetail body), §7.2 (`format` — `formatQuantity`). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/RecipeDetail.test.tsx`.

- [x] `/recipes/:id` shows ingredients in order with `formatQuantity` output (e.g. "1½ cups"); a raw converted float is never shown unformatted.
- [x] Shows steps, notes, cuisine, servings, prep/cook time. `source_url` as an "open link" when a valid URL.
- [x] Delete action → confirmation dialog → on success navigate to `/`.
- [x] Multiplier: one `Stepper` with presets ½, 1, 2, 3 and a free numeric input (`> 0`). Changing it rescales the displayed ingredient quantities. Resets to 1 on every visit to the screen.
- [x] A per-recipe made-history panel placeholder is present but empty (filled in ticket 11).
- [x] Not-found: hitting the URL for a missing recipe shows an in-content "not found" panel with a link back to the list.

**Refs:** `docs/frontend/spec.md` §10.4 (body), §7.2; plan Phase 3.

## Comments

- Branch `feat/frontend-v1-07`, PR #44 — merged as `dc4693c`. Worktree removed.
- `api/recipes.ts` untouched: `recipesApi.get` / `recipesApi.remove` already existed from Phase 0, so no adapter edit was needed.
- Ingredients sorted by `position` defensively (API already returns them ordered). Count units (`null`/`unit`/`each`) render the bare number; `null` quantity shows "to taste" plus any note.
- Multiplier reset via `key={id}` remount of the inner view.
- `/implement` two-axis review actioned: dropped an out-of-scope header Edit link and a tags line; history panel keyed on region role, not `data-testid`; count-unit label fix; "to taste" no longer suppressed by a note.
- Deliberately skipped: `asOpenableUrl` duplicated from `RecipeForm` (small pure helper; lifting to `lib/` would churn `RecipeForm` while 06c is in review); delete-failure toast (not in §10.4 but defensible under §6).
- Independent `/codex:review` still to be run by hand before merge.
