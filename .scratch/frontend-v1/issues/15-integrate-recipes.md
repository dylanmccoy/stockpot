# 15: Integrate recipes (real backend)

**What to build:** Wire the three recipe screens to the real backend and confirm recipe CRUD, the paste-and-save flow, and error mapping against it.

**Blocked by:** 05a, 06a, 06b, 06c, 07. External gate: backend Phase 3 (structured recipes) merged.

**Status:** in-review

**Files:** edit `frontend/src/test/handlers.ts`, `frontend/src/types.ts`, `docs/frontend/spec.md` §5. Run the RecipeList / RecipeForm / RecipeDetail suites against the real backend. External gate: backend Phase 3 merged.

**Spec:** `docs/spec.md` §5.2 (recipes API as merged — re-diff `types.ts` and `docs/frontend/spec.md` §5 against it); `docs/frontend/spec.md` §5 "Recipes", §10.2–§10.4. Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/RecipeList.test.tsx src/pages/RecipeForm.test.tsx src/pages/RecipeDetail.test.tsx`, then full `npm run test:run`.

- [x] RecipeList, RecipeForm, and RecipeDetail body run against the real recipes endpoints.
  (`frontend/e2e/recipes.integration.spec.ts`, the `integration` Playwright project.)
- [x] The recipes request/response shapes match `docs/spec.md` §5.2 as merged; types module and `docs/frontend/spec.md` §5 re-diffed against the backend section and any drift reconciled.
  Shapes match field-for-field — no type drift. The one gap was error *shape*: Pydantic
  union-tags a bad object ingredient element's `loc`
  (`["body","ingredients",N,"RecipeIngredientIn","item"]` + a `…,N,"str"` sibling).
  Reconciled in `lib/apiError.ts` (`normalizeLoc` / `isUnionBranchNoise`); documented in
  `docs/frontend/spec.md` §5, §6, §10.3 and the `types.ts` diff note.
- [x] Both RecipeForm flow tests pass against the real backend: create with mixed pasted-string + structured rows; edit full-replace clears removed rows; `loc`-mapped `422`s land on the right fields.
- [x] PUT full-replace confirmed to drop removed ingredient rows server-side; the ingredient-row `id` churn on PUT does not break the form.
  (Real backend probed + `recipes.integration.spec.ts` "PUT full-replace drops a removed row and survives the id churn".)
- [x] Phase 3 gate (plan) closed. (`docs/frontend/plan.md` Phase 3 + Status table.)

**Refs:** plan Phase 3 gate; `docs/frontend/spec.md` §10.2–§10.4.

## Comments

- Branch `feat/frontend-v1-15`, worktree `.claude/worktrees/frontend-v1-15`.
- `handlers.ts` needed no change — `sampleRecipe` already matches the merged
  backend shape (units not singularized; `+00:00` datetime kept per R-1, the
  real `…Z`+µs form is absorbed by `lib/format.ts`, flagged for the backend
  track). Added `errorHandlers.ingredientMemberValidation` for the union-tagged
  `422` shape instead.
- `npm run test:run` (282 pass) and `npm run test:integration` (11 pass, incl. 5
  new recipe specs) both green; typecheck + lint clean.
