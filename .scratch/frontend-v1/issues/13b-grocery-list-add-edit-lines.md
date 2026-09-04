# 13b: Grocery list — add + edit lines (vs MSW)

**What to build:** Adjusting a grocery list in the store: adding lines for things not derived from a recipe, and correcting the solver's generated lines. After this ticket a user can add a manual line and edit a generated line's item, quantity, or unit, with a quiet note when an edit reclassifies a generated line to manual.

**Blocked by:** 13a.

**Status:** done

**Files:** edit `frontend/src/pages/GroceryListDetail.tsx`, `frontend/src/pages/GroceryListDetail.test.tsx`, `frontend/src/api/grocery.ts`.

**Spec:** `docs/frontend/spec.md` §10.7 (add manual line, edit generated line — `quantity`+`unit` sent together, reclassify-to-manual note), §5 "Grocery" (`POST`/`PATCH` `/api/grocery/{id}/items`). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/GroceryListDetail.test.tsx`.

- [x] Add a manual line with an item and optional quantity/unit.
- [x] Edit a generated line's item, quantity, or unit, sending quantity and unit together.
- [x] A quiet note explains when editing a generated line reclassifies it to manual (no longer netted against stock).
- [x] Flow test (vs MSW): adding a manual line POSTs the right body and it appears in the manual group; editing a generated line's quantity sends `{ quantity, unit }` together and shows the reclassify note.

**Refs:** `docs/frontend/spec.md` §10.7; plan Phase 6. Split from ticket 13.

## Comments

- Implemented on branch `feat/frontend-v1-13b`, worktree
  `.claude/worktrees/frontend-v1-13b`. `api/grocery.ts` and `types.ts` already
  had `addItem`/`updateItem` and the DTOs from ticket 13a — no changes needed
  there.
- Add: inline "Add an item" form (Item/Quantity/Unit), always visible on an
  active list; POST omits `quantity`/`unit` when blank (no atomic pairing on
  add).
- Edit: inline per-line form (replaces the line in place), one line editing at
  a time; `quantity`+`unit` sent as an atomic pair whenever either changed
  (N6), `item` sent independently. Edit affordance hidden for frozen
  (`added_to_inventory`) lines and on an archived list.
- Reclassify note is an info-toast, fired only from a successful edit whose
  original line was `source:"generated"` — not from the checked-only PATCH
  and not when editing an already-manual line.
- `/code-review` (Standards + Spec, parallel sub-agents) ran clean: no hard
  standards violations, no spec gaps in the implementation. It flagged two
  test-coverage gaps (add-with-blank-quantity/unit untested; the
  "frozen or archived" test never actually rendered an archived list) —
  both fixed by splitting/adding tests. Judgement-call smells noted and left
  as-is: some structural duplication with `Inventory.tsx`'s
  draft/diff/validate/patch helpers (the atomic-pairing rule differs enough
  that sharing isn't obviously clean yet), and a data-clump of edit-related
  props threaded through `LineGroup`/`GroceryLine`.
- Merged via PR #68 (`feat/frontend-v1-13b`). At merge time backend CI on
  `main` was red on `test_grocery_contract.py` submit/archive cases — a
  pre-existing gap from before this ticket (`grocery.py` had submit/archive
  not yet implemented, "land in phase-6d-6e"), unrelated to this frontend
  diff; merged with admin override. `main` has since picked up phase-6d.
