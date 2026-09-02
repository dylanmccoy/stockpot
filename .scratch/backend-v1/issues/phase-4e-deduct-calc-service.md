# phase-4e: `deduct_calc` pure service + Phase 4 close

**What to build:** The pure deduction proposer `deduct_calc` — the last piece of
`inventory_math.py` that Phase 4 owns — plus closing the Phase 4 gates. No HTTP
surface yet; cook consumes it in `phase-5b`.

**Blocked by:** `phase-4d` (reuses `aggregate`), `phase-4a` (locked deduction
oracle), `phase-4c` (Phase 4 endpoint work complete).

**Status:** ready-for-agent

- [ ] `deduct_calc(reqs, stock) -> DeductProposal` in
      `backend/app/services/inventory_math.py` per §4.5: `aggregate`, a
      working-copy `live` dict, positive-only stock, the compatible bucket sorted
      ascending by row id (decision SD2), a `remaining` draw-down with
      clamp-to-zero, a `RowDeduction` list, and `_entry()` log dicts.
- [ ] `_entry(...)` returns a plain `dict` carrying **all 11 keys** on every call
      (`item, normalized_name, requested, requested_unit, deducted,
      deducted_unit, inventory_unit, before, after, applied, reason`), `null`
      where a branch does not populate one; its signature names all 11 params as
      **required** (no defaults) — omitting one is a `TypeError`.
- [ ] Branch coverage: `to taste`, `not in inventory`,
      `have uncertain (incompatible unit)`, `ok`, `clamped to 0`. `requested` is
      set only on the first row of a group, `null` after. Never a negative
      `new_quantity_base`. Cook does **not** adopt the N3 uncertainty split — it
      draws down the compatible bucket and clamps the remainder even when
      incompatible-bucket stock exists.
- [ ] Every §7 **Deduction** oracle case in `test_inventory_math.py` passes
      unchanged; the full `test_inventory_math.py` file is green.
- [ ] `cd backend && uv run pytest` green.
- [ ] Phase 4 exit criteria in `docs/phases/phase-4.md` satisfied: R-7 gate
      checked and accepted cases unchanged by the implementation passes; R-10
      scope fence (every changed behavior traces to Phase 4, its linked spec, or
      an accepted contract test); R-6 diff-review gate (a non-author reviewer
      walked every availability / aggregation / deduction branch of the Phase 4
      diff and tests against `spec.md` §7 / §5.3 / §5.5).
- [ ] `docs/plan.md` build-sequence status table: Phase 4 -> **Complete**.
- [ ] `docs/spec.md` edited only if a locked oracle proved it wrong, via a paired
      `spec.md` + contract-test change recorded per
      [`docs/plan.md` §Independent contract-test gate](../../../docs/plan.md);
      otherwise `spec.md` is untouched.
