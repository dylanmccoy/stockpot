# phase-6c: Grocery manual items + line editing (N6)

**What to build:** A grocery list can be hand-edited: add manual lines, edit a
line's substance or checked state, delete a line — with the N6 atomic
`quantity`+`unit` pair rule and reclassification. No inventory side effect;
nothing reaches stock until `submit` (`phase-6d`).

**Blocked by:** `phase-6b`.

**Status:** ready-for-agent

**Files:** edit `backend/app/routers/grocery.py` (add `/items` `POST`/`PATCH`/`DELETE`), `backend/app/schemas/grocery.py`, `backend/tests/test_grocery.py`.

**Spec:** `docs/spec.md` §5.6 (manual items + line editing, N6 atomic `quantity`+`unit` pair, reclassification to `manual`), §7 "Grocery mutation (N6)" oracle rows. Read only these sections.

**Tests:** `cd backend && uv run pytest tests/test_grocery.py`, then full `uv run pytest`.

- [ ] `POST /api/grocery/{id}/items` -> `201 GroceryListItemRead`: `404` if the
      list is absent; `409` if the list is `archived`; creates
      `GroceryListItem(source="manual", nettable=true, checked=false,
      added_to_inventory=false, normalized_name=normalize_name(item))`; manual
      amounts stored exactly as typed.
- [ ] `PATCH /api/grocery/{id}/items/{item_id}` -> `200`: `404` if the list or
      line is absent; `409` if `line.added_to_inventory` (frozen) or the list is
      `archived`; `422 "quantity and unit must be set together"` if exactly one
      of `quantity` / `unit` is present in `model_fields_set` (values may be
      `null`); apply supplied fields — `quantity` + `unit` set as-is with no
      conversion, `item` -> set + recompute `normalized_name`, `checked` -> set
      with `checked_at = _utcnow()` on `true` / `null` on `false`; **any `item` /
      `quantity` / `unit` edit reclassifies** the line `source -> "manual"`,
      `nettable -> true`; a `checked`-only PATCH does not reclassify.
- [ ] `DELETE /api/grocery/{id}/items/{item_id}` -> `204` (decision S5): `404`
      if the list or line is absent; `409` if `line.added_to_inventory` or the
      list is `archived`.
- [ ] Grocery-mutation (N6) oracle cases from `phase-6a` pass unchanged.
- [ ] `test_grocery.py`: manual item add (amounts as typed); check off ->
      inventory unchanged; on a generated `500 g` line, `PATCH {unit:"kg"}` alone
      -> `422`, `PATCH {quantity:200}` alone -> `422`,
      `PATCH {quantity:0.5, unit:"kg"}` -> `200` with `source="manual"`,
      `nettable=true`; `PATCH {item:"almond flour"}` on a generated
      `nettable=false` line -> `source="manual"`, `nettable=true`,
      `normalized_name` recomputed; `PATCH {checked:true}` alone leaves `source`
      / `nettable` unchanged; `DELETE` an unfrozen line -> `204`.
- [ ] `cd backend && uv run pytest` green.
- [ ] `docs/phases/phase-6.md` manual-item / item-edit / item-delete checkboxes
      ticked.
