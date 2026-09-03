# phase-4d: Recipe availability endpoint

**What to build:** `GET /api/recipes/{id}/availability?multiplier=` returns a
per-ingredient availability report checked against current inventory, with
correct group aggregation and the three-way uncertain / short / missing split.

**Blocked by:** `phase-4b` (needs `InventoryItem` to load stock), `phase-4a`
(locked availability + aggregation oracle).

**Status:** ready-for-agent

**Files:** edit `backend/app/services/inventory_math.py` (add `aggregate`, `check_availability`), `backend/app/routers/recipes.py` (add `GET /{id}/availability`), `backend/app/schemas/recipe.py` (availability DTOs), `backend/tests/test_recipes.py`, `backend/tests/test_validation.py`.

**Spec:** `docs/spec.md` §4 (frozen DTOs `ReqLine`/`StockRow`/`AvailabilityLineDTO`), §4.1 (`aggregate`), §4.2 (`check_availability`), §5.3 (availability endpoint), §7 availability + aggregation oracle rows. Read only these sections.

**Tests:** `cd backend && uv run pytest tests/test_recipes.py tests/test_inventory_math.py tests/test_validation.py`, then full `uv run pytest`.

- [ ] `aggregate(reqs, M)` and `check_availability(reqs, stock)` implemented in
      `backend/app/services/inventory_math.py` per §4.1 / §4.2, with the frozen
      DTOs (`ReqLine`, `StockRow`, `AvailabilityLineDTO`) from §4.
- [ ] `GET /api/recipes/{id}/availability` on the recipes router:
      `multiplier: float = Query(1.0, gt=0)`, `allow_inf_nan=False`
      (`inf` / `nan` -> `422`); `404` if the recipe is absent.
- [ ] Router builds `list[ReqLine]` with
      `quantity = None if ing.quantity is None else ing.quantity * multiplier`
      (to-taste rows stay `None`, never `None * multiplier`); loads **all**
      `inventory_items` -> `list[StockRow]`; calls `check_availability`;
      assembles `AvailabilityReport {recipe_id, multiplier, lines, all_available}`
      where `all_available` = every line with `status != "to_taste"` has
      `status == "ok"` (empty or all-to-taste recipe -> `true`).
- [ ] `AvailabilityLine` JSON matches `AvailabilityLineDTO` field for field;
      per-line `need` / `need_unit` are that row's own `quantity * M` in the
      group's canonical unit; `group_*` identical across a `group_key`.
- [ ] The §7 availability + aggregation oracle cases in `test_inventory_math.py`
      pass unchanged.
- [ ] `test_recipes.py` availability fixture gains a `"salt to taste"` line;
      `?multiplier=2` asserts per-line `need` + `group_*` canonical with
      `group_unit` present and no `have` / `short` on the line; the to-taste line
      survives scaling (no `TypeError`) and reports `status="to_taste"`; a food
      cooked/edited to `quantity_base=0` -> `missing`; a title-only recipe ->
      `lines: []` with `all_available: true`.
- [ ] `test_validation.py`: `availability?multiplier=` negative / `0` / `inf` /
      `nan` -> `422`.
- [ ] `cd backend && uv run pytest` green.
- [ ] `docs/phases/phase-4.md` availability-related Work / Verification checkboxes
      ticked.
