# 13a: Grocery list — render + optimistic check (vs MSW)

**What to build:** Working a single grocery list in a store: reading it and checking lines off with instant feedback. After this ticket a user can open `/groceries/:id`, see each line with its item and a human-formatted quantity grouped into generated and manually-added lines, see "amount uncertain" lines honestly, and tap a line to check it off with an optimistic flip that reverts on a server rejection.

**Blocked by:** 12a.

**Status:** in-review

**Files:** edit `frontend/src/pages/GroceryListDetail.tsx`, `frontend/src/api/grocery.ts`; create `frontend/src/pages/GroceryListDetail.module.css`, `frontend/src/pages/GroceryListDetail.test.tsx`. Use `frontend/src/lib/format.ts` as-is. Built against the spec DTO — **not** wired to real calls (ticket 18).

**Spec:** `docs/frontend/spec.md` §10.7 (render, optimistic check, `nettable:false` "amount uncertain"), §7.2 (`formatQuantity`), §7.4 ("uncertain" language), §5 "Grocery" (`GroceryListItemRead`). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/GroceryListDetail.test.tsx`.

- [x] `/groceries/:id` shows each line with its item and a human-formatted quantity (`formatQuantity`), grouped into generated and manually-added lines.
- [x] Tapping a line checks it off optimistically (instant), and reverts if the server rejects the change.
- [x] A line whose true shortfall is uncertain (`nettable: false`) is marked "amount uncertain" with a note to buy based on what is found — never a computed number.
- [x] The grocery calls sit behind the grocery resource adapter (R-2); built against the spec DTO, **not** wired to real calls here (that is ticket 18).
- [x] Flow test (vs MSW): lines render grouped with formatted quantities; a `nettable: false` line shows "amount uncertain" and no number; tapping a line flips it immediately, and a `409` response rolls it back.

**Refs:** `docs/frontend/spec.md` §10.7, §7.2, §7.4; plan Phase 6. Split from ticket 13.

## Comments

- Branch `feat/frontend-v1-13a`, worktree `.claude/worktrees/frontend-v1-13a`.
- New: `pages/GroceryListDetail.module.css`, `pages/GroceryListDetail.test.tsx`
  (10 flow tests). Edited: `pages/GroceryListDetail.tsx` (was the Phase-6
  placeholder). `api/grocery.ts` unchanged — `updateItem` was already present
  and spec-shaped (from 12a).
- Frozen (`added_to_inventory`) lines and archived-list lines both render a
  disabled checkbox — their `PATCH` would 409 either way, so the click is
  skipped rather than flip-and-revert.
- `/code-review since main`: Standards axis clean (one judgement-call
  duplication of RecipeDetail's `COUNT_UNITS`/`withUnitWord` helper, matching
  existing repo precedent, left as-is). Spec axis found one real gap — the
  archived-list checkbox wasn't disabled — fixed in a follow-up commit, plus a
  new test. The "you're short" apostrophe-style nit (curly vs. spec's literal
  straight quote) was left as curly to match the sibling §7.4 copy already
  implemented that way in `RecipeDetail.tsx`.
