# Phase 4 — Inventory and Availability

## Goal

Deliver inventory CRUD, canonical quantity storage, inventory math services,
and per-recipe availability checks.

## Gate

- [ ] Resolve **N5** in [`../issues.md`](../issues.md), update the normative
      behavior in `spec.md`, and close the issue before implementation.

## Specification

- [`spec.md` §1 — inventory model](../spec.md#inventory_items)
- [`spec.md` §4 — inventory math services](../spec.md#4-service-layer--backendappservicesinventory_mathpy)
- [`spec.md` §5.3 — availability](../spec.md#53-availability--get-apirecipesidavailability)
- [`spec.md` §5.5 — inventory API](../spec.md#55-inventory--routersinventorypy-prefix-apiinventory)
- Inventory rows in [`spec.md` §7](../spec.md#7-acceptance-criteria--test-matrix)

## Work

- [ ] Delete `backend/recipe.db` before running the expanded schema.
- [ ] Add `InventoryItem` with `(match_name, unit_bucket)` uniqueness,
      `quantity_base`, `display_unit`, and database checks.
- [ ] Define pure service DTOs and implement aggregation, availability,
      additive inventory proposals, and deduction proposals.
- [ ] Add `schemas/inventory.py` with separate create/update/read schemas and
      re-export them from the package.
- [ ] Implement additive POST, absolute PATCH, list, read, and delete behavior.
- [ ] Implement the recipe availability endpoint.
- [ ] Add `test_inventory.py` and `test_inventory_math.py`.

## Verification

- [ ] Known units are canonicalized and opaque units only combine exactly.
- [ ] Zero stock is absent; mixed compatible/incompatible positive stock follows
      the spec's uncertainty rule.
- [ ] POST is additive, PATCH is absolute, and identity collisions return 409.
- [ ] `cd backend && uv run pytest` passes.

## Exit criteria

- [ ] N5 is closed.
- [ ] Phase complete; update the status table in [`../plan.md`](../plan.md).
