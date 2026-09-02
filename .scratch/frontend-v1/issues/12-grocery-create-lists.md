# 12: Grocery — create + lists (vs MSW) — SPLIT

**Status:** split — do not implement this ticket directly.

Split into vertical slices:

- **12a — Create dialog.** `Dialog` from the 05b action bar: per-recipe multiplier `Stepper` (multipliers set only at create), optional name + default, deleted-recipe recovery path (re-validate `422`), success → toast + close. Blocked by 05b, 03.
- **12b — Lists index.** `/groceries` filterable active/archived (`?status=active` default), item + checked counts, open → `/groceries/:id`, delete in any status. Blocked by 04, 03.

**Downstream edges retargeted:** 13a → 12a · 18 → 12a, 12b, 13a, 13b, 13c.

**Refs:** `docs/frontend/spec.md` §10.5, §10.6; plan Phase 6.
