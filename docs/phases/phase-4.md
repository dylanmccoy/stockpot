# Phase 4 — Inventory and Availability

## Goal

Deliver inventory CRUD, canonical quantity storage, inventory math services,
and per-recipe availability checks.

## Gate

- [x] **N5 resolved** (2026-08-31) — `match_name` is a canonical server-owned key
      (`normalize_name`d on POST/PATCH, `""` → `422`, collision on normalized
      value). See [`../decisions.md`](../decisions.md#n5). Normative in `spec.md`
      §1 / §4.4 / §5.5 / §7.
- [x] **R-7 contract tests accepted before implementation** (phase-4a,
      2026-09-03) — a fresh-context reviewer writes and reviews the §7
      availability, aggregation, `add_to_inventory_calc`, and deduction oracle
      cases in `test_inventory_math.py`. Accepted cases are locked under
      [`plan.md` §Independent contract-test gate](../plan.md#independent-contract-test-gate).

## Specification

- [`spec.md` §1 — inventory model](../spec.md#inventory_items)
- [`spec.md` §4 — inventory math services](../spec.md#4-service-layer--backendappservicesinventory_mathpy)
- [`spec.md` §5.3 — availability](../spec.md#53-availability--get-apirecipesidavailability)
- [`spec.md` §5.5 — inventory API](../spec.md#55-inventory--routersinventorypy-prefix-apiinventory)
- Inventory rows in [`spec.md` §7](../spec.md#7-acceptance-criteria--test-matrix)

## Work

- [x] Delete `backend/recipe.db` before running the expanded schema. *(phase-4b)*
- [x] Add `InventoryItem` with `(match_name, unit_bucket)` uniqueness,
      `quantity_base`, `display_unit`, and database checks. *(phase-4b)*
- [ ] Define pure service DTOs and implement aggregation, availability,
      additive inventory proposals, and deduction proposals.
      *(phase-4b: DTOs + `add_to_inventory_calc` done; `aggregate` /
      `check_availability` → phase-4d, `deduct_calc` / `_entry` → phase-4e.)*
- [x] Add `schemas/inventory.py` with separate create/update/read schemas and
      re-export them from the package. *(phase-4b)*
- [ ] Implement additive POST, absolute PATCH, list, read, and delete behavior.
      `match_name` (supplied or derived) is `normalize_name`d before store;
      `""` after normalize → `422`; collision check + `ON CONFLICT` key off the
      normalized value (N5).
      *(phase-4b: additive `POST`, `GET` list, `DELETE`, and the `""`-after-normalize
      `422` done; absolute `PATCH` and the `409` collision check → phase-4c.)*
- [ ] Implement the recipe availability endpoint. Build each `ReqLine` with
      `quantity = None if ing.quantity is None else ing.quantity * multiplier`
      so a to-taste line never hits `None * multiplier` (R-1).
- [ ] Add `test_inventory.py` and any implementation-specific math regressions
      without changing the accepted `test_inventory_math.py` cases.
      `test_inventory.py` covers N5: casing / surrounding whitespace normalized,
      `""`-after-normalize → `422`, post-normalization collision → `409`,
      `"Flour"`+`"flour"` POSTs land on one row.
      *(phase-4b: `test_inventory.py` added covering casing/whitespace,
      `""`-after-normalize `422`, and `"Flour"`+`"flour"` folding; the `409`
      collision case → phase-4c with `PATCH`.)*
- [ ] Give the `test_recipes.py` availability fixture a to-taste line
      (`"salt to taste"`); assert `?multiplier=2` returns it as `status="to_taste"`
      with no `TypeError` (R-1 regression guard).

## Verification

- [ ] Every accepted §7 availability, aggregation, add-to-inventory, deduction,
      and interpretation-independent contract case passes unchanged.
- [ ] Known units are canonicalized and opaque units only combine exactly.
- [ ] Zero stock is absent; mixed compatible/incompatible positive stock follows
      the spec's uncertainty rule.
- [ ] POST is additive, PATCH is absolute, and identity collisions return 409.
- [ ] `cd backend && uv run pytest` passes.

## Exit criteria

- [x] N5 is closed (resolved 2026-08-31; see [`../decisions.md`](../decisions.md#n5)).
- [ ] The R-7 contract-test gate is checked and its accepted cases were not
      changed by the implementation pass.
- [ ] Scope fence passed (R-10, [`../plan.md` §Phase scope fence](../plan.md#phase-scope-fence-and-handoff-contract)):
      every changed behavior traces to this phase, its linked spec, or an
      accepted contract test; no deferred/context document authorized work.
- [ ] Diff review gate passed (R-6, [`../plan.md` §Execution rules](../plan.md#execution-rules)):
      a non-author reviewer walked every availability / aggregation branch in
      this phase's diff and tests against `spec.md` §7, §5.3, and §5.5.
- [ ] Phase complete; update the status table in [`../plan.md`](../plan.md).
