# phase-4e: `deduct_calc` pure service + Phase 4 close

**What to build:** The pure deduction proposer `deduct_calc` — the last piece of
`inventory_math.py` that Phase 4 owns — plus closing the Phase 4 gates. No HTTP
surface yet; cook consumes it in `phase-5b`.

**Blocked by:** `phase-4d` (reuses `aggregate`), `phase-4a` (locked deduction
oracle), `phase-4c` (Phase 4 endpoint work complete).

**Status:** done

**Files:** edit `backend/app/services/inventory_math.py` (add `deduct_calc`, `_entry`), `backend/tests/test_inventory_math.py`, `docs/phases/phase-4.md`, `docs/plan.md`.

**Spec:** `docs/spec.md` §4.5 (`deduct_calc`, `_entry`, the 11 keys, branch coverage), §4 (DTOs), §7 "Deduction" oracle rows. Read only these sections.

**Tests:** `cd backend && uv run pytest tests/test_inventory_math.py`, then full `uv run pytest`.

- [x] `deduct_calc(reqs, stock) -> DeductProposal` in
      `backend/app/services/inventory_math.py` per §4.5: `aggregate`, a
      working-copy `live` dict, positive-only stock, the compatible bucket sorted
      ascending by row id (decision SD2), a `remaining` draw-down with
      clamp-to-zero, a `RowDeduction` list, and `_entry()` log dicts.
- [x] `_entry(...)` returns a plain `dict` carrying **all 11 keys** on every call
      (`item, normalized_name, requested, requested_unit, deducted,
      deducted_unit, inventory_unit, before, after, applied, reason`), `null`
      where a branch does not populate one; its signature names all 11 params as
      **required** (no defaults) — omitting one is a `TypeError`.
- [x] Branch coverage: `to taste`, `not in inventory`,
      `have uncertain (incompatible unit)`, `ok`, `clamped to 0`. `requested` is
      set only on the first row of a group, `null` after. Never a negative
      `new_quantity_base`. Cook does **not** adopt the N3 uncertainty split — it
      draws down the compatible bucket and clamps the remainder even when
      incompatible-bucket stock exists.
- [x] Every §7 **Deduction** oracle case in `test_inventory_math.py` passes
      unchanged; the full `test_inventory_math.py` file is green.
      (`test_inventory_math.py` not edited — `git diff main` on it is empty.)
- [x] `cd backend && uv run pytest` green. (590 passed.)
- [x] Phase 4 exit criteria in `docs/phases/phase-4.md` satisfied: R-7 gate
      checked and accepted cases unchanged by the implementation passes; R-10
      scope fence (every changed behavior traces to Phase 4, its linked spec, or
      an accepted contract test); R-6 diff-review gate (a non-author reviewer
      walked every availability / aggregation / deduction branch of the Phase 4
      diff and tests against `spec.md` §7 / §5.3 / §5.5).
      (`/code-review` Standards + Spec sub-agents — no blocking findings; one
      docstring-accuracy nit actioned.)
- [x] `docs/plan.md` build-sequence status table: Phase 4 -> **Complete**.
- [x] `docs/spec.md` edited only if a locked oracle proved it wrong, via a paired
      `spec.md` + contract-test change recorded per
      [`docs/plan.md` §Independent contract-test gate](../../../docs/plan.md);
      otherwise `spec.md` is untouched. (No oracle was wrong — `spec.md`
      untouched.)

## Comments

- Branch: `feat/backend-v1-phase-4e` (off `main` @ `67544ed`).
- Worktree: `.claude/worktrees/backend-v1-phase-4e`.
- `deduct_calc` + `_entry` implemented as a near-verbatim transcription of
  `spec.md` §4.5 pseudocode. No HTTP surface — cook wires it in `phase-5b`.
- `/code-review`: Standards + Spec axes both clean. Actioned the one Standards
  nit (module docstring now carves out the `dict`-returning `deduct_calc` /
  `_entry` from the "frozen dataclasses" rule). Skipped: `_entry` call-site
  duplication + 11-arg clump + loop index `i` — all mirror the locked §4.5
  pseudocode / N7 contract; diverging would break oracle fidelity.
