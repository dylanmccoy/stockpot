# 05: Recipe list + browse (vs MSW) — SPLIT

**Status:** split — do not implement this ticket directly.

Split into vertical slices:

- **05a — Recipe list: browse, search, filter, sort.** `/` cards newest-first behind `RequireAuth`, `["recipes"]`, client-side search + cuisine/tag facets + re-sort, card → detail, add-recipe action, empty state. Blocked by 04.
- **05b — Recipe list: multi-select gather mode.** Toggle into select mode, tick recipes, running count + sticky action bar with a stubbed "create grocery list" button (the dialog is 12a). Blocked by 05a.

**Downstream edges retargeted:** 06a → 05a · 07 → 05a · 12a → 05b · 12b → 04 · 15 → 05a.

**Refs:** `docs/frontend/spec.md` §10.2; plan Phase 3.
