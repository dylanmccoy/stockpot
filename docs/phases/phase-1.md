# Phase 1 — Pure Core

## Goal

Implement and test the deterministic normalization, unit, and ingredient-parser
building blocks before they are connected to HTTP or the database.

## Specification

- [`spec.md` §2.1 — normalization](../spec.md#21-backendappnormalizepy)
- [`spec.md` §2.2 — units](../spec.md#22-backendappunitspy)
- [`spec.md` §2.3 — ingredient parsing](../spec.md#23-backendappservicesingredient_parsepy)
- Applicable rows in [`spec.md` §7](../spec.md#7-acceptance-criteria--test-matrix)

## Work

- [ ] Add `backend/app/normalize.py`.
- [ ] Add `backend/app/units.py`.
- [ ] Add `backend/app/services/__init__.py` and `ingredient_parse.py`.
- [ ] Keep these modules pure: no ORM, session, request, or network imports.
- [ ] Build and unit-test `parse_ingredient` here, but do not wire it to recipe
      routes until Phase 3.
- [ ] Add `test_units.py`.
- [ ] Add `test_ingredient_parse.py`.

## Verification

- [ ] The parser acceptance table passes exactly.
- [ ] Known, count, opaque, and incompatible unit behavior is covered.
- [ ] `cd backend && uv run pytest` passes.

## Exit criteria

- [ ] No HTTP or database behavior changed in this phase.
- [ ] Phase complete; update the status table in [`../plan.md`](../plan.md).
