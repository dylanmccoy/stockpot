# Phase 1 — Pure Core

## Goal

Implement and test the deterministic normalization, unit, and ingredient-parser
building blocks before they are connected to HTTP or the database.

## Specification

- [`spec.md` §2.1 — normalization](../spec.md#21-backendappnormalizepy)
- [`spec.md` §2.2 — units](../spec.md#22-backendappunitspy)
- [`spec.md` §2.3 — ingredient parsing](../spec.md#23-backendappservicesingredient_parsepy)
- Applicable rows in [`spec.md` §7](../spec.md#7-acceptance-criteria--test-matrix)

## Gate

- [ ] **R-7 contract tests accepted before implementation** — a fresh-context
      reviewer translates the §2.1–2.3 exact tables and invariants into
      `test_normalize.py`, `test_units.py`, and `test_ingredient_parse.py`; the
      expected values are reviewed before production code changes. These cases
      are then locked under [`plan.md` §Independent contract-test gate](../plan.md#independent-contract-test-gate).

## Work

- [ ] Add `backend/app/normalize.py`. Factor the §2.1 step-5 singularization rule
      into `_singularize_token(tok) -> str`; `normalize_name` calls it on the
      final token (R-3).
- [ ] Add `backend/app/units.py`. `normalize_unit_token` calls
      `normalize._singularize_token` on the whole (lowered, stripped) string — no
      second, near-duplicate rule (R-3).
- [ ] Add `backend/app/services/__init__.py` and `ingredient_parse.py`.
- [ ] Keep these modules pure: no ORM, session, request, or network imports.
- [ ] Build and unit-test `parse_ingredient` here, but do not wire it to recipe
      routes until Phase 3.
- [ ] Add any implementation-specific regression coverage without editing or
      deleting the independently accepted cases in `test_normalize.py`,
      `test_units.py`, or `test_ingredient_parse.py`.

## Verification

- [ ] The parser acceptance table passes exactly.
- [ ] Every locked normalization, conversion, and `add_quantities` oracle passes;
      first-seen partition order and the §2 floating tolerance are enforced.
- [ ] The deterministic parser corpus and all interpretation-independent §2
      checks pass; global name-normalization idempotence is not asserted (D1).
- [ ] Known, count, opaque, and incompatible unit behavior is covered.
- [ ] Every synonym-table token and every opaque token round-trips through
      `normalize_unit_token` to a resolvable form (`cups→cup`, `lbs→lb`,
      `boxes→box`, `dashes→dash`); the 5 `-es`-group opaque plurals are asserted
      by name (R-3).
- [ ] `cd backend && uv run pytest` passes.

## Exit criteria

- [ ] The R-7 contract-test gate is checked and its accepted cases were not
      changed by the implementation pass.
- [ ] No HTTP or database behavior changed in this phase.
- [ ] Scope fence passed (R-10, [`../plan.md` §Phase scope fence](../plan.md#phase-scope-fence-and-handoff-contract)):
      every changed behavior traces to this phase, its linked spec, or an
      accepted contract test; no deferred/context document authorized work.
- [ ] Diff review gate passed (R-6, [`../plan.md` §Execution rules](../plan.md#execution-rules)):
      a non-author reviewer checked this phase's diff and new tests against
      `spec.md` §7 and §§2.1–2.3.
- [ ] Phase complete; update the status table in [`../plan.md`](../plan.md).
