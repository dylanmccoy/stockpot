# 11: Made-history (vs MSW) — SPLIT

**Status:** split — do not implement this ticket directly.

Split into vertical slices:

- **11a — Shared accordion + per-recipe panel.** `CookLogRow` + `DeductionDetail` accordion (five reason chips incl. amber; no-deduction case); per-recipe panel in `/recipes/:id`, newest first, unpaginated, `["recipe-cook-logs", id]`. Blocked by 07, 10.
- **11b — Global `/history` screen.** Paginated "load more" + count, `["cook-logs", { limit, offset }]`, per-row recipe link, deleted-recipe title as plain text; reuses 11a's row. Blocked by 11a.

**Downstream edges retargeted:** 17 → 10, 11a, 11b.

**Refs:** `docs/frontend/spec.md` §10.8; plan Phase 5.
