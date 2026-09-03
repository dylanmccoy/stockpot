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

- [ ] Delete `backend/recipe.db` before running the expanded schema.
- [ ] Add `CookLog` with recipe-title and deduction snapshots.
- [ ] Add cook request and log response schemas, including `CookDeductionRead`
      (`BaseModel`, `model_config = ConfigDict(extra="forbid")`, `reason` a
      `Literal` of the 5 allowed strings); `CookLogRead.deductions` is
      `list[CookDeductionRead]`. Define `_entry()` with all 11 params required
      (no defaults) (N7).
- [ ] Implement cook with `deduct=true` and log-only `deduct=false` modes.
      Build each `ReqLine` with
      `quantity = None if ing.quantity is None else ing.quantity * multiplier`
      so a to-taste line never hits `None * multiplier` (R-1).
- [ ] Apply service proposals inside the request's single transaction.
- [ ] Add per-recipe made-history reads.
- [ ] Add paginated global list and detail routes that survive recipe deletion.
- [ ] Add remaining cook/history coverage without changing the accepted
      contract cases, including the file-backed HTTP cook race. The `/cook`
      fixture recipe carries a to-taste line (`"salt to taste"`); assert it
      scales with `multiplier` without `TypeError` and yields a `"to taste"`
      deduction entry that is never applied (R-1 regression guard).

## Verification

- [ ] Every accepted §7 cook, audit-log, and cook-race contract case passes
      unchanged.
- [ ] Deduction amounts and before/after snapshots use canonical units.
- [ ] Deduction clamps at zero and reports every non-applied reason consistently.
- [ ] Every `deductions[]` entry validates against `CookDeductionRead`; all 5
      `reason` values exercised; a stored entry with an extra key or unlisted
      `reason` → `500` on read.
- [ ] Concurrent cooks do not lose an update.
- [ ] `cd backend && uv run pytest` passes.

## Exit criteria

- [x] N7 is closed (resolved 2026-08-31; see [`../decisions.md`](../decisions.md#n7)).
- [ ] The R-7 contract-test gate is checked and its accepted cases were not
      changed by the implementation pass.
- [ ] Scope fence passed (R-10, [`../plan.md` §Phase scope fence](../plan.md#phase-scope-fence-and-handoff-contract)):
      every changed behavior traces to this phase, its linked spec, or an
      accepted contract test; no deferred/context document authorized work.
- [ ] Diff review gate passed (R-6, [`../plan.md` §Execution rules](../plan.md#execution-rules)):
      a non-author reviewer walked every deduction / clamp-to-zero / reason
      branch in this phase's diff and tests against `spec.md` §7, §4.5, and §5.4.
- [ ] Phase complete; update the status table in [`../plan.md`](../plan.md).
