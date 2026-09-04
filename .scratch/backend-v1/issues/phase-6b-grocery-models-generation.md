# phase-6b: Grocery models + list generation

**What to build:** `POST /api/grocery` turns selected recipes into a persisted
grocery list of consolidated, canonical, netted shortfalls; lists can be read
(with `?status`) and deleted. Manual items, line editing, submit, and archive
land in later Phase 6 tickets.

**Blocked by:** `phase-6a`.

**Status:** done

**Files:** create `backend/app/schemas/grocery.py`, `backend/app/routers/grocery.py`, `backend/tests/test_grocery.py`; edit `backend/app/models.py` (add `GroceryList`, `GroceryListItem`), `backend/app/services/inventory_math.py` (add `generate_lines`), `backend/app/schemas/__init__.py`, `backend/app/main.py`, `backend/tests/test_validation.py`.

**Spec:** `docs/spec.md` §1 "grocery_lists"/"grocery_list_items" (models), §4.3 (`generate_lines`, netting table, output order), §5.6 (`POST`/`GET`/`DELETE` grocery), §7 Grocery generation oracle rows. Read only these sections.

**Tests:** `cd backend && uv run pytest tests/test_grocery.py tests/test_inventory_math.py tests/test_validation.py`, then full `uv run pytest`.

- [x] `backend/recipe.db` deleted (schema expansion).
- [x] `GroceryList` + `GroceryListItem` models per §1: all columns incl.
      `source_recipe_ids` JSON (no FK), `nettable` (default `true`),
      `added_to_inventory` (default `false`, idempotency + freeze flag),
      `applied_quantity` / `applied_unit`, `checked_at` / `submitted_at`;
      `items` relationship `cascade="all, delete-orphan"` ordered by `id`; item
      FK `ON DELETE CASCADE` `passive_deletes=True`.
- [x] `backend/app/schemas/grocery.py` (`GroceryListCreate`, `GroceryListItemIn`,
      `GroceryListItemUpdate`, `GroceryListItemRead`, `GroceryListRead`) per §5.6;
      re-exported from `app.schemas`.
- [x] `generate_lines(reqs_by_recipe, stock) -> list[GroceryLineDTO]` in
      `backend/app/services/inventory_math.py` per §4.3: consolidate via
      `add_quantities`; canonical `need_base`; the netting table (compatible
      covers -> no line; compatible short + no incompatible -> shortfall
      `nettable=true`; compatible short + incompatible present -> compatible-bucket
      remainder `nettable=false`; no compatible + incompatible present -> full
      need `nettable=false`; no positive stock -> full need `nettable=true`;
      unquantified opaque / `None` -> `quantity=null` `nettable=false`; entirely
      to-taste -> `quantity=null, unit=null` `nettable=false`); output order =
      first-seen normalized-name then first-seen partition.
- [x] `backend/app/routers/grocery.py` (`prefix="/api/grocery"`,
      `route_class=TransactionRoute`, auth):
  - `POST /api/grocery` -> `201 GroceryListRead`: validate `recipe_ids`
    non-empty + unique + all exist -> `422`; `multipliers` keys subset of
    `recipe_ids`, values `> 0` finite -> `422`; build `ReqLine` per recipe (in
    `recipe_ids` order) with
    `quantity = None if ing.quantity is None else ing.quantity * multipliers.get(rid, 1)`;
    load all inventory -> `StockRow`; call `generate_lines`; persist
    `GroceryList(name or "Groceries <UTC date>", status="active",
    source_recipe_ids=recipe_ids)` with one generated
    `GroceryListItem(source="generated", checked=false,
    added_to_inventory=false, nettable/normalized_name/quantity/unit from the DTO)`.
  - `GET /api/grocery` -> `200 list[GroceryListRead]`, optional
    `?status=active|archived`, order `created_at DESC, id DESC`.
  - `GET /api/grocery/{id}` -> `200 GroceryListRead` / `404`.
  - `DELETE /api/grocery/{id}` -> `204`, any status, cascades items.
- [x] Router registered; route-class guard green.
- [x] `generate_lines` oracle cases in `test_inventory_math.py` pass unchanged.
- [x] `backend/tests/test_grocery.py`: generate from 2 selected recipes
      (consolidation + netting; generated `quantity` / `unit` canonical); a
      to-taste ingredient (`quantity=None`) survives `multipliers` scaling (no
      `TypeError`) and emits a `quantity=null, unit=null` line; a food cooked to
      `quantity_base=0` still produces a full-need line; delete list cascades
      items; a non-nettable line is present; N3: `need 3 can` / `1 can + 1 jar`
      -> a `2 can` line `nettable=false`; `1 can` only -> `nettable=true`.
- [x] `test_validation.py`: `recipe_ids` empty or with a duplicate -> `422`; a
      `multipliers` key not in `recipe_ids` -> `422`; `multipliers` value `0` /
      `inf` / `nan` -> `422`.
- [ ] `cd backend && uv run pytest` green. Not fully: `test_grocery_contract.py`
      (the `phase-6a` locked oracle) has 20 expected failures in its PATCH /
      submit / archive / submit-race sections — those routes are `phase-6c`-`6e`
      scope, and that file's own docstring says it "does not fully pass until
      `phase-6d` (submit) / `phase-6e` (archive)". Every other file, including
      the three named above, is green.
- [x] `docs/phases/phase-6.md` model / `generate_lines` / list-create-read-delete
      checkboxes ticked.

## Comments

- Implemented on `feat/backend-v1-phase-6b` (worktree:
  `.claude/worktrees/backend-v1-phase-6b`), reviewed with `/code-review since
  main` (Standards + Spec both clean), opened as
  [PR #64](https://github.com/dylanmccoy/stockpot/pull/64), and squash-merged
  to `main` at `bd06e95`.
