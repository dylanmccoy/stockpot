# phase-5a: Cook contract-test lock (R-7)

**What to build:** A locked, independently-reviewed black-box test slice for
cooking, audit-log serialization, and the cook race — authored from
`docs/spec.md` §4.5 / §5.4 / §6 / §7 only, in a fresh context, before Phase 5
production code.

**Blocked by:** `phase-4e` (Phase 4 complete).

**Status:** ready-for-agent

- [ ] §7 cook + audit-log contract cases authored black-box from `spec.md` into
      the appropriate module(s) (`test_inventory_math.py` additions and/or a cook
      contract test): the deduction outcomes for `deduct=true`, the
      `CookDeductionRead` JSON shape (all 11 keys, `reason` in the 5-value
      `Literal`, `null` only where the §5.4 table permits), and a stored entry
      with an extra/unknown key or an unlisted `reason` -> `500` on read (N7).
- [ ] The cook-race contract specified: a file-backed HTTP two-`cook` race does
      not lose an update; concurrent writers serialize (second `BEGIN` blocks;
      with `busy_timeout` lowered -> `database is locked` -> `409`, not `500`).
- [ ] Reviewed and accepted as **locked** per
      [`docs/plan.md` §Independent contract-test gate](../../../docs/plan.md);
      the acceptance is recorded.
- [ ] `docs/phases/phase-5.md` R-7 gate checkbox ticked.
- [ ] Not expected to pass until `phase-5b`.
