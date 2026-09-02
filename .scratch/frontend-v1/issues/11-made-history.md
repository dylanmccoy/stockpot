# 11: Made-history (vs MSW)

**What to build:** Two views of past cooks sharing one row component — a panel inside the recipe detail screen and a global paginated history screen. After this ticket a user can see how many times a recipe was made and when, expand any cook to its per-ingredient deduction detail, and browse a household-wide activity log.

**Blocked by:** 07, 10.

**Status:** ready-for-agent

- [ ] A shared `CookLogRow` + `DeductionDetail` accordion: collapsed shows date, who cooked it, the multiplier, and whether stock was deducted; expanded shows a per-ingredient table (requested, deducted, before, after) with a plain-language reason chip per ingredient covering all five reasons, including the amber "check what you have".
- [ ] A cook logged without deduction shows "logged — stock not changed" with no detail table.
- [ ] The per-recipe panel in `/recipes/:id` lists every cook of that recipe, newest first, unpaginated, with no recipe-title column. Query key `["recipe-cook-logs", id]`.
- [ ] `/history` lists every cook across all recipes, newest first, paginated with a "load more" and a count of how many exist. Query key `["cook-logs", { limit, offset }]`.
- [ ] Each `/history` row names its recipe and links to it; if that recipe was deleted, its title still shows as plain text.

**Refs:** `docs/frontend/spec.md` §10.8; plan Phase 5.
