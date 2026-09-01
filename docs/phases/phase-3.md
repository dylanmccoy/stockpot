# Phase 3 — Structured Recipes

## Goal

Replace the flat recipe skeleton with nested recipe data and support both
structured and pasted-string ingredient input.

## Specification

- [`spec.md` §1 — recipes and recipe ingredients](../spec.md#1-data-model--backendappmodelspy)
- [`spec.md` §5.2 — recipe CRUD](../spec.md#52-recipes-crud--routersrecipespy-prefix-apirecipes)
- Recipe and validation rows in [`spec.md` §7](../spec.md#7-acceptance-criteria--test-matrix)

## Work

- [ ] Delete `backend/recipe.db` before running the expanded schema.
- [ ] Expand `Recipe` and add `RecipeIngredient` with ordered child rows.
- [ ] Keep `photo_path` reserved and nullable; make `raw_text` active for pasted
      ingredient input.
- [ ] Add `schemas/recipe.py` to the schema package created in Phase 2 and
      re-export its public schemas.
- [ ] Implement nested create/read/replace/delete behavior.
- [ ] Parse string ingredient elements and preserve their verbatim `raw_text`.
      Truncate a pasted `str` element to 200 chars before `parse_ingredient` —
      the single guard that keeps `raw_text` / `item` / `note` within their
      columns (R-4).
- [ ] Add validation for finite positive quantities and bounded list/text fields.
- [ ] Expand `test_recipes.py` and add `test_validation.py`.

## Verification

- [ ] Ingredient positions are server-assigned, contiguous, and stable on read.
- [ ] PUT replaces old ingredient children without leaving orphan rows.
- [ ] Ingredient IDs may churn on PUT; no API contract depends on their stability.
- [ ] String and object ingredient forms round-trip as specified.
- [ ] A pasted line over 200 chars is truncated to 200 before parsing; the
      recipe still creates and every stored string field fits its column (R-4).
- [ ] `cd backend && uv run pytest` passes.

## Exit criteria

- [ ] Scope fence passed (R-10, [`../plan.md` §Phase scope fence](../plan.md#phase-scope-fence-and-handoff-contract)):
      every changed behavior traces to this phase and its linked spec; no
      deferred/context document authorized work.
- [ ] Diff review gate passed (R-6, [`../plan.md` §Execution rules](../plan.md#execution-rules)):
      a non-author reviewer checked this phase's diff and new tests against
      `spec.md` §7 and §5.2.
- [ ] Phase complete; update the status table in [`../plan.md`](../plan.md).
