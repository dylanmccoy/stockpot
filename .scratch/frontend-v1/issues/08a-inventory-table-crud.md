# 08a: Inventory table + add + delete (vs MSW)

**What to build:** Seeing what the household has in stock and adding or removing items. After this ticket a user can open `/inventory`, read the stock table ordered by match name, add stock through a form (with copy explaining that matching an existing item + unit tops up that row rather than duplicating it), and delete an item behind a confirmation.

**Blocked by:** 04, 03.

**Status:** ready-for-agent

**Files:** edit `frontend/src/pages/Inventory.tsx`, `frontend/src/api/inventory.ts`; create `frontend/src/pages/Inventory.module.css`, `frontend/src/pages/Inventory.test.tsx`.

**Spec:** `docs/frontend/spec.md` §10.9 (Inventory), §5 "Inventory" (`/api/inventory` shapes). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/Inventory.test.tsx`.

- [ ] `/inventory` renders a table: item, match name, unit bucket, quantity in a sensible unit, last-updated; ordered by match name. Query key `["inventory"]`.
- [ ] Add form: item name, quantity, unit, optional match name; copy explains that adding stock matching an existing item + unit increases that row (additive upsert, server-side).
- [ ] On add success the table refetches and reflects the new or topped-up row.
- [ ] Delete → confirmation dialog → `DELETE` → row gone.
- [ ] Flow test (vs MSW): table renders from `["inventory"]`; a valid add POSTs the right body and refetches; delete confirms then removes the row.

**Refs:** `docs/frontend/spec.md` §10.9; plan Phase 4. Split from ticket 08.
