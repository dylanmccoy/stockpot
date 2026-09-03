# 08a: Inventory table + add + delete (vs MSW)

**What to build:** Seeing what the household has in stock and adding or removing items. After this ticket a user can open `/inventory`, read the stock table ordered by match name, add stock through a form (with copy explaining that matching an existing item + unit tops up that row rather than duplicating it), and delete an item behind a confirmation.

**Blocked by:** 04, 03.

**Status:** in-review

**Files:** edit `frontend/src/pages/Inventory.tsx`, `frontend/src/api/inventory.ts`; create `frontend/src/pages/Inventory.module.css`, `frontend/src/pages/Inventory.test.tsx`.

**Spec:** `docs/frontend/spec.md` §10.9 (Inventory), §5 "Inventory" (`/api/inventory` shapes). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/Inventory.test.tsx`.

- [x] `/inventory` renders a table: item, match name, unit bucket, quantity in a sensible unit, last-updated; ordered by match name. Query key `["inventory"]`.
- [x] Add form: item name, quantity, unit, optional match name; copy explains that adding stock matching an existing item + unit increases that row (additive upsert, server-side).
- [x] On add success the table refetches and reflects the new or topped-up row.
- [x] Delete → confirmation dialog → `DELETE` → row gone.
- [x] Flow test (vs MSW): table renders from `["inventory"]`; a valid add POSTs the right body and refetches; delete confirms then removes the row.

**Refs:** `docs/frontend/spec.md` §10.9; plan Phase 4. Split from ticket 08.

## Comments

- Branch `feat/frontend-v1-08a`, worktree `.claude/worktrees/frontend-v1-08a`.
- `frontend/src/api/inventory.ts` needed no change — `list` / `create` / `remove`
  were already on the adapter. Only `Inventory.tsx` + new `.module.css` /
  `.test.tsx`.
- Pure seams exported for tests: `buildInventoryCreate`, `validateAddDraft`
  (client guards that only block guaranteed-422s), `sortInventory` (defensive
  case-insensitive re-sort mirroring the server order), `stockLabel`
  (`formatQuantity` + trailing display unit — the AC's "sensible unit").
- Add errors: 422 field/form via `useFormErrors`; a `409` add conflict is
  toast + refetch with the §6 catalog copy (not the bare "conflict" banner the
  string-`detail` rule alone would give).
- Out of scope (ticket 08b): inline quantity edit, PATCH-rule enforcement, the
  prominent `match_name` editor with 409. `inventoryApi.update` left unwired.
- `/code-review` (Standards + Spec): no hard violations. Actioned — renamed the
  draft-merge helper `patch` → `setField` (avoids colliding with 08b's HTTP
  PATCH), added the 409 toast+refetch path, swapped the plain loading `<p>` for
  an `sr-only` status + skeleton block to match sibling pages, gave `.errorPanel`
  an explicit `color` token. Skipped (deliberate): `stockLabel` appending the
  unit is the AC intent; the defensive client re-sort is the house idiom
  (matches `RecipeDetail`); two 3-line `onError` handlers don't warrant a shared
  helper.
