# 13c: Grocery list — submit into inventory + archive (vs MSW)

**What to build:** Closing out a grocery list: submitting checked lines back into stock in a deliberate, repeatable step, and archiving the finished list. After this ticket a user can submit checked lines into inventory via a dialog that explains the change is additive and cannot be undone, keep shopping and submit again for newly-checked lines, see already-submitted lines frozen with the amount that was added, and archive the list.

**Blocked by:** 13a, 08a.

**Status:** done

**Files:** edit `frontend/src/pages/GroceryListDetail.tsx`, `frontend/src/pages/GroceryListDetail.test.tsx`, `frontend/src/api/grocery.ts`. Use `frontend/src/components/Dialog.tsx`.

**Spec:** `docs/frontend/spec.md` §10.7 (submit dialog, frozen `applied_*` lines, archive, `409`), §10.9 (inventory invalidation), §5 "Grocery" (`/submit`, `/archive`). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/GroceryListDetail.test.tsx`.

- [x] Submit checked lines into inventory via a `Dialog` that explains this adds stock and cannot be undone. Shopping can continue and submit again later for newly-checked lines.
- [x] On submit success the inventory query is invalidated and refetches.
- [x] Already-submitted lines are read-only, show the amount that was added (`applied_*`), and are un-editable / un-deletable without a confusing error.
- [x] Archive a finished list. Acting on a list archived by someone else shows a clear message to refetch and move on (`409`).
- [x] Flow test (vs MSW): check two lines → submit → lines frozen with `applied_*` and inventory invalidated; `PATCH` a frozen line → conflict copy; archive → list status archived; a `409` on archive → refetch message. (Split across several focused `it`s rather than one mega-test, per existing file convention — same scenarios covered.)

**Refs:** `docs/frontend/spec.md` §10.7, §10.9; plan Phase 6. Split from ticket 13.

## Comments

Implemented on `feat/frontend-v1-13c` in worktree
`.claude/worktrees/frontend-v1-13c`. 8 new test cases added to
`GroceryListDetail.test.tsx` (23 total, all passing); full frontend suite
(349 tests), typecheck, and lint all green. Two-axis `/code-review` run
against `main`: Standards found no hard violations (two minor
judgement-call duplication notes, left as-is); Spec found no missing
requirements or scope creep, one latent-coupling note actioned (a comment
on the `isStockConflict` reuse in the item-PATCH conflict handler,
`GroceryListDetail.tsx`).
