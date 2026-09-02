# 08: Inventory (vs MSW) — SPLIT

**Status:** split — do not implement this ticket directly.

Split into vertical slices:

- **08a — Table + add + delete.** `/inventory` table ordered by match name, `["inventory"]`; add form with additive-upsert copy; delete behind a confirmation. Blocked by 04, 03.
- **08b — Inline edit, PATCH rules, match_name editor.** Inline quantity edit (confirm unit); client-side enforcement of the three PATCH rules before the request; prominent `match_name` editor with an inline `409` on in-bucket collision. Blocked by 08a.

**Downstream edges retargeted:** 10 → 08a · 13a → (12a only) · 13c → 08a · 16 → 08a, 08b.

**Refs:** `docs/frontend/spec.md` §10.9; plan Phase 4.
