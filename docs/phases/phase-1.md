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

- [x] **R-7 contract tests accepted before implementation** — a fresh-context
      reviewer translates the §2.1–2.3 exact tables and invariants into
      `test_normalize.py`, `test_units.py`, and `test_ingredient_parse.py`; the
      expected values are reviewed before production code changes. These cases
      are then locked under [`plan.md` §Independent contract-test gate](../plan.md#independent-contract-test-gate).

## Work

- [x] Add `backend/app/normalize.py`. Factor the §2.1 step-5 singularization rule
      into `_singularize_token(tok) -> str`; `normalize_name` calls it on the
      final token (R-3).
- [x] Add `backend/app/units.py`. `normalize_unit_token` calls
      `normalize._singularize_token` on the whole (lowered, stripped) string — no
      second, near-duplicate rule (R-3).
- [x] Add `backend/app/services/__init__.py` and `ingredient_parse.py`.
- [x] Keep these modules pure: no ORM, session, request, or network imports.
- [x] Build and unit-test `parse_ingredient` here, but do not wire it to recipe
      routes until Phase 3.
- [x] Add any implementation-specific regression coverage without editing or
      deleting the independently accepted cases in `test_normalize.py`,
      `test_units.py`, or `test_ingredient_parse.py`.

## Verification

- [x] The parser acceptance table passes exactly.
- [x] Every locked normalization, conversion, and `add_quantities` oracle passes;
      first-seen partition order and the §2 floating tolerance are enforced.
- [x] The deterministic parser corpus and all interpretation-independent §2
      checks pass; global name-normalization idempotence is not asserted (D1).
- [x] Known, count, opaque, and incompatible unit behavior is covered.
- [x] Every synonym-table token and every opaque token round-trips through
      `normalize_unit_token` to a resolvable form (`cups→cup`, `lbs→lb`,
      `boxes→box`, `dashes→dash`); the 5 `-es`-group opaque plurals are asserted
      by name (R-3).
- [x] `cd backend && uv run pytest` passes.

## Exit criteria

- [x] The R-7 contract-test gate is checked and its accepted cases were not
      changed by the implementation pass.
- [x] No HTTP or database behavior changed in this phase.
- [x] Scope fence passed (R-10, [`../plan.md` §Phase scope fence](../plan.md#phase-scope-fence-and-handoff-contract)):
      every changed behavior traces to this phase, its linked spec, or an
      accepted contract test; no deferred/context document authorized work.
- [x] Diff review gate passed (R-6, [`../plan.md` §Execution rules](../plan.md#execution-rules)):
      a non-author reviewer checked this phase's diff and new tests against
      `spec.md` §7 and §§2.1–2.3.
- [x] Phase complete; update the status table in [`../plan.md`](../plan.md).

## Outcome

- Contract tests (`test_normalize.py`, `test_units.py`, `test_ingredient_parse.py`)
  authored and accepted in **#15** before any production code; a fresh-context
  Codex pass reviewed the expected values.
- Implementation (`app/normalize.py`, `app/units.py`,
  `app/services/ingredient_parse.py`) landed in **#16**, on the accepted
  oracles without altering them.
- R-6 / R-10 review: three Codex rounds against the impl diff — two P2 parser
  findings (`fl oz` two-word synonym; unified `\bto\s+taste\b` matcher) folded
  into #16, final round clean.
- `cd backend && uv run pytest` → 335 passed. No HTTP or DB behavior touched;
  parser is not wired into any route (deferred to Phase 3).
