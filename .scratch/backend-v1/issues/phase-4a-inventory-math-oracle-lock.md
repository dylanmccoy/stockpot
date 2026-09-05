# phase-4a: Inventory math contract-test lock (R-7)

**What to build:** A locked, independently-reviewed black-box test slice for the
pure inventory-math layer, authored from `docs/spec.md` §4 and §7 only (not from
any implementation), in a fresh context, before a single line of Phase 4
production code. This is the frozen oracle every later Phase 4 math ticket must
satisfy without editing it.

**Blocked by:** None (Phase 3 complete; N5 already resolved). Can start immediately.

**Status:** done

- [ ] `backend/tests/test_inventory_math.py` created, authored black-box from
      `spec.md` §4 / §7.
- [ ] Every §7 **Availability** oracle row asserted exactly: missing, compatible
      short, mixed-bucket uncertain short, compatible-covers-despite-other-bucket,
      only-incompatible, zero-stock-is-absent, duplicate-members-aggregate-once,
      canonical mass, to taste.
- [ ] Every §7 **Deduction** oracle row asserted exactly: not-in-inventory,
      only-incompatible, enough compatible, clamp compatible, compatible-wins-over-
      incompatible, ascending row-ID draw — plus the to-taste entry shape.
- [ ] Every §7 **Add-to-inventory proposal** row asserted exactly, including the
      negative-amount pure-service clamp.
- [ ] §7 interpretation-independent invariants asserted: per-member `group_*` /
      status / `nettable` repeat identically; no negative `new_quantity_base`;
      `before - deducted == after` within the §2 tolerance; inventory-input
      reorder does not change availability or grocery values; deduction order is
      ascending row ID, not input order.
- [ ] Extra required cases from the §7 `test_inventory_math.py` row: `clove` need
      vs `bulb` stock -> `have_uncertain`; canonical `requested`/`deducted`/
      `deducted_unit`; kg-from-g (stock `2000 g`, recipe `1 kg` -> `deducted 1000`,
      `after 1000`, all `g`).
- [ ] Every deduction log entry asserted to carry all 11 keys and to round-trip
      through `CookDeductionRead`; `_entry` requires every kwarg (a missing one is
      a `TypeError`) (N7).
- [ ] Reviewed and accepted as **locked** per
      [`docs/plan.md` §Independent contract-test gate](../../../docs/plan.md);
      the acceptance is recorded (commit or PR).
- [ ] `docs/phases/phase-4.md` R-7 gate checkbox ticked.
- [ ] Not expected to pass yet — no implementation exists. CI need not be green on
      this file until `phase-4d` / `phase-4e`. A case later found wrong changes
      only via a paired `spec.md` + test change per the gate.
