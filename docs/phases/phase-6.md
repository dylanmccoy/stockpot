# Phase 6 — Grocery Lists

## Goal

Generate persisted grocery shortfalls from selected recipes and safely submit
checked lines into inventory.

## Gate

- [x] **N6 resolved** (2026-08-31) — grocery-line PATCH treats `quantity` + `unit`
      as an atomic pair (one without the other → `422`, no conversion), and any
      `item` / `quantity` / `unit` edit reclassifies the line `source → "manual"`,
      `nettable → true`. See [`../decisions.md`](../decisions.md#n6). Normative in
      `spec.md` §5.6 / §7.
- [x] **R-7 contract tests accepted before implementation** (phase-6a,
      2026-09-03) — a fresh-context reviewer writes and reviews the §7
      `generate_lines`, grocery mutation (N6), submit, and submit-race contract
      cases before route/model implementation: the `generate_lines` oracle rows
      as the **Grocery generation** section of
      `backend/tests/test_inventory_math.py`, and the N6 / submit / submit-race
      cases as `backend/tests/test_grocery_contract.py`. Both fail on collection
      until `phase-6b` (the `generate_lines` / `app.schemas.grocery` imports) —
      that is the lock. Accepted cases are locked under
      [`plan.md` §Independent contract-test gate](../plan.md#independent-contract-test-gate).

## Specification

- [`spec.md` §1 — grocery models](../spec.md#grocery_lists)
- [`spec.md` §4.3 — line generation](../spec.md#43-generate_linesreqs_by_recipe-listlistreqline-stock-liststockrow---listgrocerylinedto)
- [`spec.md` §5.6 — grocery API](../spec.md#56-grocery-lists--routersgrocerypy-prefix-apigrocery)
- [`spec.md` §6 — transactions](../spec.md#6-concurrency--transactions)
- Grocery rows in [`spec.md` §7](../spec.md#7-acceptance-criteria--test-matrix)

## Work

- [x] Delete `backend/recipe.db` before running the expanded schema.
- [x] Add grocery-list and grocery-list-item models with applied snapshots.
- [x] Implement pure consolidated shortfall generation. Build each `ReqLine` with
      `quantity = None if ing.quantity is None else ing.quantity * multipliers.get(rid, 1)`
      so a to-taste line never hits `None * multiplier` (R-1).
- [x] Add `schemas/grocery.py`, re-export its public schemas, and implement
      list/create/read/delete routes.
- [x] Add manual-item create, item edit, and item delete behavior. On PATCH:
      reject a body with exactly one of `quantity` / `unit` (`model_fields_set`)
      → `422 "quantity and unit must be set together"`; any `item` / `quantity` /
      `unit` edit sets `source="manual"`, `nettable=true` (a `checked`-only PATCH
      does not) (N6).
- [x] Implement forward-only submit with line freezing and no auto-archive.
- [x] Implement explicit guarded archive.
- [x] Add remaining `test_grocery.py` coverage without changing the accepted
      contract cases, including the file-backed HTTP submit race. A generate
      fixture recipe carries a to-taste line; assert it scales with `multipliers`
      without `TypeError` and emits a `quantity=null, unit=null` line (R-1
      regression guard). N6: on a generated `500 g` line, `PATCH {unit:"kg"}`
      alone and `PATCH {quantity:200}` alone → `422`; `PATCH {quantity:0.5,
      unit:"kg"}` → `200` with `source="manual"`, `nettable=true`, and `submit`
      adds `0.5 kg`, not `500 kg`; `PATCH {item:...}` on a `nettable=false` line
      → `source="manual"`, `nettable=true`; `PATCH {checked:true}` leaves both.
- [x] **Rewrite `test_concurrency.py` to the §7 contract.** (phase-6f) The
      version specified before review pass 8 cannot fail: `BEGIN IMMEDIATE` on
      every transaction (§3.2) makes the lost-update interleave unconstructable,
      so the test passes vacuously. Asserts instead the properties that make the
      race impossible — serialization (a second `BEGIN` blocks and, with
      `busy_timeout` lowered, raises `database is locked`), the `409` mapping of
      that error through HTTP, and freshness after the first writer commits.
      Keeps the threaded two-`cook` HTTP test as a smoke check, not as the
      guard, and adds a matching file-backed HTTP submit-race smoke.

## Verification

- [x] Every accepted §7 generation, grocery-mutation, submit, and submit-race
      contract case passes unchanged.
- [x] Generated lines are consolidated, canonical, and correctly marked when
      incompatible positive stock makes the shortfall uncertain.
- [x] Checking a line has no inventory side effect; submit applies it once.
- [x] Frozen and archived mutations return 409 as specified.
- [x] Concurrent submits apply each checked line at most once.
- [x] `test_concurrency.py` asserts serialization, the `409` lock mapping, and
      post-commit freshness — not an interleave that cannot occur.
- [x] `cd backend && uv run pytest` passes.

## Exit criteria

- [x] N6 is closed (resolved 2026-08-31; see [`../decisions.md`](../decisions.md#n6)).
- [x] The R-7 contract-test gate is checked and its accepted cases were not
      changed by the implementation pass. (phase-6f, 2026-09-04 — `test_
      inventory_math.py` and `test_grocery_contract.py` diffed byte-identical
      since the phase-6a lock commit `fac0edf`.)
- [x] Scope fence passed (R-10, [`../plan.md` §Phase scope fence](../plan.md#phase-scope-fence-and-handoff-contract)):
      every changed behavior traces to this phase, its linked spec, or an
      accepted contract test; no deferred/context document authorized work.
- [x] Diff review gate passed (R-6, [`../plan.md` §Execution rules](../plan.md#execution-rules)):
      a non-author reviewer walked every consolidation / shortfall-uncertainty /
      submit branch in this phase's diff and tests against `spec.md` §7 and §5.6.
      (phase-6f, 2026-09-04 — two-axis review since `fac0edf`: Standards 0 hard
      violations / 4 minor pre-existing judgement smells; Spec 0
      critical/major / 2 minor / 2 nitpick, locked-oracle values confirmed
      unchanged. Two pre-existing minor spec-fidelity notes from phase-6e,
      accepted as-is rather than reopening this phase (neither is a behavior
      change, so R-10 doesn't apply): `archive_grocery_list` uses
      read-then-set instead of §5.6's literal guarded-`UPDATE` pseudocode
      (behaviorally equivalent under §6's whole-transaction locking);
      `update_grocery_item` rejects `item: null` with `422`, a defensive check
      §5.6 doesn't state.)
- [x] Backend behavior is feature-complete.
- [x] Phase complete; update the status table in [`../plan.md`](../plan.md).
