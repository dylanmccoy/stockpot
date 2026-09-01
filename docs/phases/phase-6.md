# Phase 6 — Grocery Lists

## Goal

Generate persisted grocery shortfalls from selected recipes and safely submit
checked lines into inventory.

## Gate

- [ ] Resolve **N6** in [`../issues.md`](../issues.md), update grocery edit
      semantics in `spec.md`, and close the issue before implementation.

## Specification

- [`spec.md` §1 — grocery models](../spec.md#grocery_lists)
- [`spec.md` §4.3 — line generation](../spec.md#43-generate_linesreqs_by_recipe-listlistreqline-stock-liststockrow---listgrocerylinedto)
- [`spec.md` §5.6 — grocery API](../spec.md#56-grocery-lists--routersgrocerypy-prefix-apigrocery)
- [`spec.md` §6 — transactions](../spec.md#6-concurrency--transactions)
- Grocery rows in [`spec.md` §7](../spec.md#7-acceptance-criteria--test-matrix)

## Work

- [ ] Delete `backend/recipe.db` before running the expanded schema.
- [ ] Add grocery-list and grocery-list-item models with applied snapshots.
- [ ] Implement pure consolidated shortfall generation.
- [ ] Add `schemas/grocery.py`, re-export its public schemas, and implement
      list/create/read/delete routes.
- [ ] Add manual-item create, item edit, and item delete behavior.
- [ ] Implement forward-only submit with line freezing and no auto-archive.
- [ ] Implement explicit guarded archive.
- [ ] Add `test_grocery.py` and the file-backed HTTP submit race.

## Verification

- [ ] Generated lines are consolidated, canonical, and correctly marked when
      incompatible positive stock makes the shortfall uncertain.
- [ ] Checking a line has no inventory side effect; submit applies it once.
- [ ] Frozen and archived mutations return 409 as specified.
- [ ] Concurrent submits apply each checked line at most once.
- [ ] `cd backend && uv run pytest` passes.

## Exit criteria

- [ ] N6 is closed.
- [ ] Backend behavior is feature-complete.
- [ ] Phase complete; update the status table in [`../plan.md`](../plan.md).
