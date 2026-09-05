# phase-4b: InventoryItem model + additive CRUD

**What to build:** Inventory rows exist and can be listed, created, read, and
deleted through `/api/inventory`. `POST` is an additive upsert — posting the same
item twice sums the quantities into one row. The absolute-replacement `PATCH`
lands in `phase-4c`.

**Blocked by:** `phase-4a` (locked add-to-inventory oracle).

**Status:** done

**Files:** create `backend/app/schemas/inventory.py`, `backend/app/routers/inventory.py`, `backend/tests/test_inventory.py`; edit `backend/app/models.py` (add `InventoryItem`), `backend/app/services/inventory_math.py` (add `add_to_inventory_calc`), `backend/app/schemas/__init__.py`, `backend/app/main.py`, `backend/tests/test_validation.py`.

**Spec:** `docs/spec.md` §1 "inventory_items" (model), §5.5 (inventory `GET`/`POST`/`DELETE`, additive upsert), §4.4 (`add_to_inventory_calc`), §2.2 (`bucket_of`, `normalize_unit_token`). Read only these sections.

**Tests:** `cd backend && uv run pytest tests/test_inventory.py tests/test_inventory_math.py tests/test_validation.py`, then full `uv run pytest`.

- [ ] `backend/recipe.db` deleted before the first run (schema expansion).
- [ ] `InventoryItem` model per `spec.md` §1: `item`, `normalized_name`,
      `match_name` (indexed), `unit_bucket` `str(30)`, `quantity_base` `Float`
      with `CHECK(quantity_base >= 0)` and finite, `display_unit` nullable,
      `updated_at` (`default` / `onupdate` `_utcnow`), `created_by_id` nullable
      with no cascade; `UNIQUE (match_name, unit_bucket)`.
- [ ] `backend/app/schemas/inventory.py` with `InventoryItemCreate`,
      `InventoryItemUpdate`, `InventoryItemRead` per §5.5; re-exported from
      `app.schemas`. `InventoryItemRead` includes computed `display_quantity`.
- [ ] `add_to_inventory_calc(match_name, display_item, amount, unit) ->
      InventoryDelta` in `backend/app/services/inventory_math.py` per §4.4:
      bucket via `bucket_of(normalize_unit_token(unit))`, `max(amount, 0.0)`,
      canonical `add_base`, `canonical_added` `Quantity`, canonical `match_name`
      from `normalize_name(match_name or display_item)`.
- [ ] `backend/app/routers/inventory.py` (`prefix="/api/inventory"`,
      `route_class=TransactionRoute`, `Depends(get_current_user)`):
  - `GET /api/inventory` -> `200 list[InventoryItemRead]`,
    `order_by(match_name ASC, unit_bucket ASC)`.
  - `POST /api/inventory` -> `201`: additive via `add_to_inventory_calc` +
    `sqlite_insert(...).on_conflict_do_update(...)` per §5.5 — sum
    `quantity_base`, `COALESCE(excluded.display_unit, ...)`, `updated_at` bound to
    one `_utcnow()` on both branches; `item` / `normalized_name` /
    `created_by_id` untouched on conflict; `422` when `match_name` (supplied or
    derived) normalizes to `""`.
  - `DELETE /api/inventory/{id}` -> `204`; `404` if the row is absent.
- [ ] Router registered in `create_app` / `app.main`; the `test_transactions.py`
      route-class guard stays green (new router is a `TransactionRoute`).
- [ ] `backend/tests/test_inventory.py` covers: two `POST`s to one
      `(match_name, unit_bucket)` sum in `quantity_base`; `POST` missing `item`
      or `quantity` -> `422`; cross-unit add merges via `quantity_base`; same
      food in two incompatible units -> two rows; `POST` `"Flour"` then
      `"flour"` (same unit) hit one row; `match_name` `"  "` / `"!!!"` -> `422`;
      negative / non-finite `quantity` -> `422` (also in `test_validation.py`).
- [ ] The add-to-inventory oracle cases in `test_inventory_math.py` (from
      `phase-4a`) pass unchanged.
- [ ] `cd backend && uv run pytest` green.
- [ ] `docs/phases/phase-4.md` Work / Verification checkboxes for the model,
      schema, additive POST, list, read, and delete behavior ticked.
