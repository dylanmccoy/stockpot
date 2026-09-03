# 12a: Grocery — create dialog (vs MSW)

**What to build:** Turning recipes ticked on the recipe list into a named grocery list, with a per-recipe multiplier set at creation. After this ticket a user in multi-select mode can open a create dialog, set a multiplier per selected recipe, name the list (or take the default), and generate it; a recipe deleted meanwhile gives a recovery path.

**Blocked by:** 05b, 03.

**Status:** ready-for-agent

**Files:** edit `frontend/src/pages/RecipeList.tsx` (wire the 05b multi-select stub), `frontend/src/pages/RecipeList.test.tsx`, `frontend/src/api/grocery.ts`; create a create-dialog component (`frontend/src/pages/GroceryCreateDialog.tsx` + `.module.css`) using `frontend/src/components/Dialog.tsx` + `Stepper.tsx`. Built against the spec DTO — **not** wired to real calls (ticket 18).

**Spec:** `docs/frontend/spec.md` §10.5 (grocery create dialog), §5 "Grocery" (`POST /api/grocery` body — `recipe_ids`, `multipliers`, `422`). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/RecipeList.test.tsx`.

- [ ] A grocery-create `Dialog` launches from the recipe-list multi-select action bar, wiring the stub from ticket 05b.
- [ ] The dialog collects a multiplier `Stepper` per selected recipe (default 1×) — the only place multipliers are set, since `POST /api/grocery` accepts them only at create — and an optional list name with a sensible default.
- [ ] If a selected recipe was deleted meanwhile, the dialog gives a recovery path: drop it from the selection and continue (re-validate against the `422`).
- [ ] On success: show a confirmation toast and close the dialog (optionally navigate to the `/groceries/:id` placeholder). No dependency on the `/groceries` index (ticket 12b).
- [ ] The grocery calls sit behind the grocery resource adapter (R-2); built against the spec DTO, **not** wired to real calls here (that is ticket 18).
- [ ] Flow test (vs MSW): select two recipes, set multipliers + a name, submit → correct `POST /api/grocery` body; a `422` for a missing `recipe_id` → drop it via the recovery path → resubmit succeeds.

**Refs:** `docs/frontend/spec.md` §10.5; plan Phase 6. Split from ticket 12.
