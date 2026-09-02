# 06: Recipe create / edit form (vs MSW) — SPLIT

**Status:** split — do not implement this ticket directly.

Split into vertical slices:

- **06a — Form scaffold + create.** One form at `/recipes/new`: scalars, ordered steps (up/down), unified ingredient table (add/remove/reorder, blank qty = to taste), POST → redirect, `source_url` open-link, `loc`-mapped `422` under fields + form-level banner. `/recipes/:id/edit` stays on the placeholder. Blocked by 05a, 03.
- **06b — Paste ingredients with preview.** "Paste ingredients" → `parseIngredients` → parsed-row preview → append on confirm → hand-fix; mixed string/object `ingredients` array on save. Blocked by 06a.
- **06c — Edit / PUT full-replace.** `/recipes/:id/edit` pre-fills from the recipe; save is `PUT` full-replace so removed rows go away; row-`id` churn doesn't break the table. Blocked by 06a.

**Downstream edges retargeted:** 15 → 05a, 06a, 06b, 06c, 07.

**Refs:** `docs/frontend/spec.md` §7.1, §10.3; plan Phase 3.
