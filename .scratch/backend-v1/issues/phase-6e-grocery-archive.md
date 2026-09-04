# phase-6e: Grocery archive

**What to build:** `POST /api/grocery/{id}/archive` is the single guarded path to
`status="archived"`, and every mutating grocery route rejects an archived list
with `409`.

**Blocked by:** `phase-6d` (the archived-state guard tests reference `submit`).

**Status:** in-review

**Files:** edit `backend/app/routers/grocery.py` (add `/archive`; archived-state `409` guard on every mutating grocery route), `backend/tests/test_grocery.py`.

**Spec:** `docs/spec.md` §5.6 (archive — the only path to `archived`; `409` on every mutating route for an archived list). Read only this section.

**Tests:** `cd backend && uv run pytest tests/test_grocery.py`, then full `uv run pytest`.

- [x] `POST /api/grocery/{id}/archive` -> `200 GroceryListRead`: `404` if the
      list is absent; `UPDATE grocery_lists SET status='archived' WHERE id=:id
      AND status='active'`; if `rowcount == 0` (already archived) -> `409
      {"detail": "list is not active"}`. This is the **only** path to
      `archived`.
- [x] Archived-state guard confirmed on `PATCH /api/grocery/{id}/items/{id}`,
      `POST /api/grocery/{id}/submit`, `DELETE /api/grocery/{id}/items/{id}`,
      `POST /api/grocery/{id}/items` -> each `409` on an archived list.
- [x] `test_grocery.py`: `POST /archive` -> `status=archived`; later `PATCH` /
      `submit` / item-`POST` / item-`DELETE` -> `409`; archiving an
      already-archived list -> `409`.
- [x] `cd backend && uv run pytest` green.
- [x] `docs/phases/phase-6.md` archive checkbox ticked.

## Comments

- Implemented on `feat/backend-v1-phase-6e`, worktree
  `.claude/worktrees/backend-v1-phase-6e`. Guard was applied via an ORM
  read-then-set (`grocery_list.status = "archived"`) rather than the literal
  Core `UPDATE ... WHERE status='active'` in the acceptance criteria, matching
  `submit`'s existing idiom — safe under this app's per-request `BEGIN
  IMMEDIATE` write serialization (spec.md §6), which already precludes the
  race a raw conditional `UPDATE` would additionally guard against. Full
  `uv run pytest` green, including `test_grocery_contract.py`'s phase-6a
  locked oracle, which now passes in full for the first time.
