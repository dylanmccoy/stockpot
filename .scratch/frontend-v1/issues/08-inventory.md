# 08: Inventory (vs MSW)

**What to build:** Managing what the household has in stock. After this ticket a user can see the inventory table, add stock (which adds to an existing row rather than duplicating), edit a quantity inline under the backend's PATCH rules, edit the prominent match name, and delete an item — each rejection shown inline.

**Blocked by:** 04, 03.

**Status:** ready-for-agent

- [ ] `/inventory` renders a table: item, match name, unit bucket, quantity in a sensible unit, last-updated; ordered by match name. Query key `["inventory"]`.
- [ ] Add form: item name, quantity, unit, optional match name; copy explains that adding stock matching an existing item + unit increases that row (additive upsert).
- [ ] Inline quantity edit requires confirming the unit on save.
- [ ] Client-side rule enforcement before PATCH: a quantity change forces a unit; a unit cannot change to one in a different bucket; a null unit is rejected for a non-COUNT item.
- [ ] `match_name` editor is prominent, saves in normalized form, has a short hint explaining it links inventory to recipe ingredients, and shows an inline error on an in-bucket collision (`409`).
- [ ] Delete → confirmation.
- [ ] Flow test (vs MSW): the four PATCH-rejection rules each return the expected inline error; a valid `{ quantity, unit }` PATCH updates the row; a `match_name` collision shows inline.

**Refs:** `docs/frontend/spec.md` §10.9; plan Phase 4.
