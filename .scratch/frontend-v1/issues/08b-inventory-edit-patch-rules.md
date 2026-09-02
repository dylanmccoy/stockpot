# 08b: Inventory — inline edit, PATCH rules, match_name editor (vs MSW)

**What to build:** Editing a stock quantity and its match name under the backend's PATCH constraints, with every rejection shown inline. After this ticket a user can edit a quantity inline (confirming the unit), is stopped client-side before a guaranteed-reject PATCH, and can edit the prominent match name with an in-bucket collision surfaced inline.

**Blocked by:** 08a.

**Status:** ready-for-agent

- [ ] Inline quantity edit requires confirming the unit on save.
- [ ] Client-side rule enforcement before PATCH: a quantity change forces a unit; a unit cannot change to one in a different bucket; a null unit is rejected for a non-COUNT item.
- [ ] `match_name` editor is prominent, saves in normalized form, has a short hint explaining it links inventory to recipe ingredients, and shows an inline error on an in-bucket collision (`409`).
- [ ] Flow test (vs MSW): the three client-side rejections each block the PATCH and show the inline reason; a valid `{ quantity, unit }` PATCH updates the row; a `match_name` `409` shows inline.

**Refs:** `docs/frontend/spec.md` §10.9; plan Phase 4. Split from ticket 08.
