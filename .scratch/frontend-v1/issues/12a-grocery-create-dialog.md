# 12a: Grocery — create dialog (vs MSW)

**What to build:** Turning recipes ticked on the recipe list into a named grocery list, with a per-recipe multiplier set at creation. After this ticket a user in multi-select mode can open a create dialog, set a multiplier per selected recipe, name the list (or take the default), and generate it; a recipe deleted meanwhile gives a recovery path.

**Blocked by:** 05b, 03.

**Status:** done

**Files:** edit `frontend/src/pages/RecipeList.tsx` (wire the 05b multi-select stub), `frontend/src/pages/RecipeList.test.tsx`, `frontend/src/api/grocery.ts`; create a create-dialog component (`frontend/src/pages/GroceryCreateDialog.tsx` + `.module.css`) using `frontend/src/components/Dialog.tsx` + `Stepper.tsx`. Built against the spec DTO — **not** wired to real calls (ticket 18).

**Spec:** `docs/frontend/spec.md` §10.5 (grocery create dialog), §5 "Grocery" (`POST /api/grocery` body — `recipe_ids`, `multipliers`, `422`). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/RecipeList.test.tsx`.

- [x] A grocery-create `Dialog` launches from the recipe-list multi-select action bar, wiring the stub from ticket 05b.
- [x] The dialog collects a multiplier `Stepper` per selected recipe (default 1×) — the only place multipliers are set, since `POST /api/grocery` accepts them only at create — and an optional list name with a sensible default.
- [x] If a selected recipe was deleted meanwhile, the dialog gives a recovery path: drop it from the selection and continue (re-validate against the `422`).
- [x] On success: show a confirmation toast and close the dialog (navigates to `/groceries/:id`). No dependency on the `/groceries` index (ticket 12b).
- [x] The grocery calls sit behind the grocery resource adapter (R-2); built against the spec DTO, **not** wired to real calls here (that is ticket 18). `groceryApi.create` already existed — no adapter change needed.
- [x] Flow test (vs MSW): select two recipes, set multipliers + a name, submit → correct `POST /api/grocery` body; a `422` for a missing `recipe_id` → drop it via the recovery path → resubmit succeeds.

**Refs:** `docs/frontend/spec.md` §10.5; plan Phase 6. Split from ticket 12.

## Comments

- Branch `feat/frontend-v1-12a`, worktree `.claude/worktrees/frontend-v1-12a`.
- New: `pages/GroceryCreateDialog.tsx` (+ `.module.css`). Edited: `pages/RecipeList.tsx`
  (wired the 05b `createGroceryList` stub to the dialog), `pages/RecipeList.test.tsx`.
- `api/grocery.ts` unchanged — `create` was already present and spec-shaped.
- The "which ids vanished" detection re-diffs the selection against a fresh
  `["recipes"]` fetch (spec §10.5 / R-13), not the `422` body.
