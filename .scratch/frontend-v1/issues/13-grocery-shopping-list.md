# 13: Grocery — shopping a list (vs MSW) — SPLIT

**Status:** split — do not implement this ticket directly.

Split into vertical slices:

- **13a — Render + optimistic check.** `/groceries/:id` lines with human-formatted quantities, grouped generated/manual, "amount uncertain" lines (`nettable: false`), optimistic check/uncheck with rollback on rejection. Blocked by 12a.
- **13b — Add + edit lines.** Add a manual line; edit a generated line's item/quantity/unit (quantity + unit sent together) with a reclassify-to-manual note. Blocked by 13a.
- **13c — Submit into inventory + archive.** Submit checked lines via a `Dialog` (additive, no undo, repeatable), inventory invalidated, submitted lines frozen with `applied_*`, archive a finished list, `409` when archived elsewhere. Blocked by 13a, 08a.

**Downstream edges retargeted:** 18 → 12a, 12b, 13a, 13b, 13c.

**Refs:** `docs/frontend/spec.md` §10.7, §7.4; plan Phase 6.
