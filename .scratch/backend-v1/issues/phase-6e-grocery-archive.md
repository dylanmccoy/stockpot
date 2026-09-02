# phase-6e: Grocery archive

**What to build:** `POST /api/grocery/{id}/archive` is the single guarded path to
`status="archived"`, and every mutating grocery route rejects an archived list
with `409`.

**Blocked by:** `phase-6d` (the archived-state guard tests reference `submit`).

**Status:** ready-for-agent

- [ ] `POST /api/grocery/{id}/archive` -> `200 GroceryListRead`: `404` if the
      list is absent; `UPDATE grocery_lists SET status='archived' WHERE id=:id
      AND status='active'`; if `rowcount == 0` (already archived) -> `409
      {"detail": "list is not active"}`. This is the **only** path to
      `archived`.
- [ ] Archived-state guard confirmed on `PATCH /api/grocery/{id}/items/{id}`,
      `POST /api/grocery/{id}/submit`, `DELETE /api/grocery/{id}/items/{id}`,
      `POST /api/grocery/{id}/items` -> each `409` on an archived list.
- [ ] `test_grocery.py`: `POST /archive` -> `status=archived`; later `PATCH` /
      `submit` / item-`POST` / item-`DELETE` -> `409`; archiving an
      already-archived list -> `409`.
- [ ] `cd backend && uv run pytest` green.
- [ ] `docs/phases/phase-6.md` archive checkbox ticked.
