# 12b: Grocery — lists index (vs MSW)

**What to build:** Managing the set of grocery lists. After this ticket a user can open `/groceries`, see all their lists filtered by status with item and checked counts, open one, and delete one in any status.

**Blocked by:** 04, 03.

**Status:** ready-for-agent

**Files:** edit `frontend/src/pages/GroceryLists.tsx`, `frontend/src/api/grocery.ts`; create `frontend/src/pages/GroceryLists.module.css`, `frontend/src/pages/GroceryLists.test.tsx`. Built against the spec DTO — **not** wired to real calls (ticket 18).

**Spec:** `docs/frontend/spec.md` §10.6 (GroceryLists index — status filter, counts, delete), §5 "Grocery" (`GET /api/grocery?status=`, `GroceryListRead`). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/GroceryLists.test.tsx`.

- [ ] `/groceries` lists the user's grocery lists, filterable to active or archived (`?status=active` default), with item and checked counts per list.
- [ ] A list can be opened (→ `/groceries/:id`) and deleted in any status with a confirmation.
- [ ] Empty state when the user has no lists in the current filter.
- [ ] The grocery calls sit behind the grocery resource adapter (R-2); built against the spec DTO, **not** wired to real calls here (that is ticket 18).
- [ ] Flow test (vs MSW): the index renders lists with counts; switching to archived sends `?status=archived`; delete confirms then removes the list.

**Refs:** `docs/frontend/spec.md` §10.6; plan Phase 6. Split from ticket 12.
