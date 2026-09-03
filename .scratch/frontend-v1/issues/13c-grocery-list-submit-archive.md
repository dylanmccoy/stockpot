# 13c: Grocery list — submit into inventory + archive (vs MSW)

**What to build:** Closing out a grocery list: submitting checked lines back into stock in a deliberate, repeatable step, and archiving the finished list. After this ticket a user can submit checked lines into inventory via a dialog that explains the change is additive and cannot be undone, keep shopping and submit again for newly-checked lines, see already-submitted lines frozen with the amount that was added, and archive the list.

**Blocked by:** 13a, 08a.

**Status:** ready-for-agent

**Files:** edit `frontend/src/pages/GroceryListDetail.tsx`, `frontend/src/pages/GroceryListDetail.test.tsx`, `frontend/src/api/grocery.ts`. Use `frontend/src/components/Dialog.tsx`.

**Spec:** `docs/frontend/spec.md` §10.7 (submit dialog, frozen `applied_*` lines, archive, `409`), §10.9 (inventory invalidation), §5 "Grocery" (`/submit`, `/archive`). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/GroceryListDetail.test.tsx`.

- [ ] Submit checked lines into inventory via a `Dialog` that explains this adds stock and cannot be undone. Shopping can continue and submit again later for newly-checked lines.
- [ ] On submit success the inventory query is invalidated and refetches.
- [ ] Already-submitted lines are read-only, show the amount that was added (`applied_*`), and are un-editable / un-deletable without a confusing error.
- [ ] Archive a finished list. Acting on a list archived by someone else shows a clear message to refetch and move on (`409`).
- [ ] Flow test (vs MSW): check two lines → submit → lines frozen with `applied_*` and inventory invalidated; `PATCH` a frozen line → conflict copy; archive → list status archived; a `409` on archive → refetch message.

**Refs:** `docs/frontend/spec.md` §10.7, §10.9; plan Phase 6. Split from ticket 13.
