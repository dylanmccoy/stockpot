# Phase 5 — Cooking and History

## Goal

Record every cooking event, optionally deduct inventory without lost updates,
and keep logs readable after recipe deletion.

## Gate

- [x] **N7 resolved** (2026-08-31) — `CookDeductionRead` is a real Pydantic model
      (`extra="forbid"`, `reason` a 5-value `Literal`), used as
      `CookLogRead.deductions: list[CookDeductionRead]`; the DB column stays raw
      `JSON list[dict]`, validated on read. `_entry()` takes all 11 kwargs as
      required. See [`../decisions.md`](../decisions.md#n7). Normative in
      `spec.md` §1 / §4.5 / §5.4 / §7.
- [x] **R-7 contract tests accepted before implementation** (phase-5a,
      2026-09-03) — a fresh-context reviewer writes and reviews the §7 cook,
      audit-log, and cook-race contract cases before route/model implementation,
      as `backend/tests/test_cook_contract.py` (fails on collection until
      `phase-5b` — that is the lock). Accepted cases are locked under
      [`plan.md` §Independent contract-test gate](../plan.md#independent-contract-test-gate).

## Specification

- [`spec.md` §1 — cook logs](../spec.md#cook_logs)
- [`spec.md` §4.5 — deduction proposals](../spec.md#45-deduct_calcreqs-listreqline-stock-liststockrow---deductproposal)
- [`spec.md` §5.4 — cook and history API](../spec.md#54-cook--made-history)
- [`spec.md` §6 — transactions](../spec.md#6-concurrency--transactions)
- Cook-log rows in [`spec.md` §7](../spec.md#7-acceptance-criteria--test-matrix)

## Work

- [x] Delete `backend/recipe.db` before running the expanded schema. (phase-5b)
- [x] Add `CookLog` with recipe-title and deduction snapshots. (phase-5b)
- [x] Add cook request and log response schemas, including `CookDeductionRead`
      (`BaseModel`, `model_config = ConfigDict(extra="forbid")`, `reason` a
      `Literal` of the 5 allowed strings); `CookLogRead.deductions` is
      `list[CookDeductionRead]`. Define `_entry()` with all 11 params required
      (no defaults) (N7). (phase-5b — `_entry()` already lived in
      `services/inventory_math.py` from phase-4e)
- [x] Implement cook with `deduct=true` and log-only `deduct=false` modes.
      Build each `ReqLine` with
      `quantity = None if ing.quantity is None else ing.quantity * multiplier`
      so a to-taste line never hits `None * multiplier` (R-1). (phase-5b)
- [x] Apply service proposals inside the request's single transaction. (phase-5b —
      Core `UPDATE ... SET quantity_base=?, updated_at=?`, `_utcnow()` bound explicitly)
- [x] Add per-recipe made-history reads. (phase-5b —
      `GET /api/recipes/{id}/cook-logs`)
- [x] Add paginated global list and detail routes that survive recipe deletion.
      (phase-5c — `routers/cook_logs.py`: `GET /api/cook-logs` →
      `CookLogList {items, total, limit, offset}` (`limit 1..200`, `offset ≥ 0`,
      `422` out of range, order `cooked_at DESC, id DESC`) and
      `GET /api/cook-logs/{log_id}` → `CookLogRead` / `404`; both resolve after
      the recipe is deleted)
- [x] Add remaining cook/history coverage without changing the accepted
      contract cases, including the file-backed HTTP cook race. The `/cook`
      fixture recipe carries a to-taste line (`"salt to taste"`); assert it
      scales with `multiplier` without `TypeError` and yields a `"to taste"`
      deduction entry that is never applied (R-1 regression guard). (phase-5b —
      `test_recipes.py` cook section + `test_concurrency.py`)

## Verification

- [x] Every accepted §7 cook, audit-log, and cook-race contract case passes
      unchanged. (phase-5b — `test_cook_contract.py`, 53 cases, no expected
      value altered)
- [x] Deduction amounts and before/after snapshots use canonical units. (phase-5b)
- [x] Deduction clamps at zero and reports every non-applied reason consistently.
      (phase-5b)
- [x] Every `deductions[]` entry validates against `CookDeductionRead`; all 5
      `reason` values exercised; a stored entry with an extra key or unlisted
      `reason` → `500` on read. (phase-5b)
- [x] Concurrent cooks do not lose an update. (phase-5b —
      `test_concurrency.py` + `test_cook_contract.py` section D)
- [x] `cd backend && uv run pytest` passes. (phase-5b — 654 passed;
      phase-5c — 664 passed, `test_cook_logs.py` added)

## Exit criteria

- [x] N7 is closed (resolved 2026-08-31; see [`../decisions.md`](../decisions.md#n7)).
- [x] The R-7 contract-test gate is checked and its accepted cases were not
      changed by the implementation pass. (phase-5c — `test_cook_contract.py`
      untouched; `test_cook_logs.py` is additive and covers only the §5.4
      global-read surface.)
- [x] Scope fence passed (R-10, [`../plan.md` §Phase scope fence](../plan.md#phase-scope-fence-and-handoff-contract)):
      every changed behavior traces to this phase, its linked spec, or an
      accepted contract test; no deferred/context document authorized work.
      (phase-5c — new code is `routers/cook_logs.py` + `CookLogList`, both named
      by `spec.md` §5.4.)
- [x] Diff review gate passed (R-6, [`../plan.md` §Execution rules](../plan.md#execution-rules)):
      a non-author reviewer walked every deduction / clamp-to-zero / reason
      branch in this phase's diff and tests against `spec.md` §7, §4.5, and §5.4.
      (phase-5b covered the deduction branches; phase-5c `/code-review` walked
      the read-only global-feed diff — pagination bounds, ordering, count,
      recipe-deletion survival — against `spec.md` §5.4.)
- [x] Phase complete; update the status table in [`../plan.md`](../plan.md).
