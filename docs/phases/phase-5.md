# Phase 5 — Cooking and History

## Goal

Record every cooking event, optionally deduct inventory without lost updates,
and keep logs readable after recipe deletion.

## Gate

- [ ] Resolve **N7** in [`../issues.md`](../issues.md), update the normative
      deduction response shape in `spec.md`, and close the issue first.

## Specification

- [`spec.md` §1 — cook logs](../spec.md#cook_logs)
- [`spec.md` §4.5 — deduction proposals](../spec.md#45-deduct_calcreqs-listreqline-stock-liststockrow---deductproposal)
- [`spec.md` §5.4 — cook and history API](../spec.md#54-cook--made-history)
- [`spec.md` §6 — transactions](../spec.md#6-concurrency--transactions)
- Cook-log rows in [`spec.md` §7](../spec.md#7-acceptance-criteria--test-matrix)

## Work

- [ ] Delete `backend/recipe.db` before running the expanded schema.
- [ ] Add `CookLog` with recipe-title and deduction snapshots.
- [ ] Add cook request and log response schemas.
- [ ] Implement cook with `deduct=true` and log-only `deduct=false` modes.
- [ ] Apply service proposals inside the request's single transaction.
- [ ] Add per-recipe made-history reads.
- [ ] Add paginated global list and detail routes that survive recipe deletion.
- [ ] Add cook/history tests and the file-backed HTTP cook race.

## Verification

- [ ] Deduction amounts and before/after snapshots use canonical units.
- [ ] Deduction clamps at zero and reports every non-applied reason consistently.
- [ ] Concurrent cooks do not lose an update.
- [ ] `cd backend && uv run pytest` passes.

## Exit criteria

- [ ] N7 is closed.
- [ ] Phase complete; update the status table in [`../plan.md`](../plan.md).
