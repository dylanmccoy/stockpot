# phase-4d: Recipe availability endpoint

**What to build:** `GET /api/recipes/{id}/availability?multiplier=` returns a
per-ingredient availability report checked against current inventory, with
correct group aggregation and the three-way uncertain / short / missing split.

**Blocked by:** `phase-4b` (needs `InventoryItem` to load stock), `phase-4a`
(locked availability + aggregation oracle).

**Status:** in-review

**Files:** edit `backend/app/services/inventory_math.py` (add `aggregate`, `check_availability`), `backend/app/routers/recipes.py` (add `GET /{id}/availability`), `backend/app/schemas/recipe.py` (availability DTOs), `backend/tests/test_recipes.py`, `backend/tests/test_validation.py`.

**Spec:** `docs/spec.md` §4 (frozen DTOs `ReqLine`/`StockRow`/`AvailabilityLineDTO`), §4.1 (`aggregate`), §4.2 (`check_availability`), §5.3 (availability endpoint), §7 availability + aggregation oracle rows. Read only these sections.

**Tests:** `cd backend && uv run pytest tests/test_recipes.py tests/test_inventory_math.py tests/test_validation.py`, then full `uv run pytest`.

- [x] `aggregate(reqs, M)` and `check_availability(reqs, stock)` implemented in
      `backend/app/services/inventory_math.py` per §4.1 / §4.2, with the frozen
      DTOs (`ReqLine`, `StockRow`, `AvailabilityLineDTO`) from §4.
      (`aggregate` takes `M=1.0` default — `ReqLine.quantity` already has the
      multiplier folded per §4.2; internal `GroupAgg` helper dataclass.)
- [x] `GET /api/recipes/{id}/availability` on the recipes router:
      `multiplier: float = Query(1.0, gt=0)`, `allow_inf_nan=False`
      (`inf` / `nan` -> `422`); `404` if the recipe is absent.
- [x] Router builds `list[ReqLine]` with
      `quantity = None if ing.quantity is None else ing.quantity * multiplier`
      (to-taste rows stay `None`, never `None * multiplier`); loads **all**
      `inventory_items` -> `list[StockRow]`; calls `check_availability`;
      assembles `AvailabilityReport {recipe_id, multiplier, lines, all_available}`
      where `all_available` = every line with `status != "to_taste"` has
      `status == "ok"` (empty or all-to-taste recipe -> `true`).
- [x] `AvailabilityLine` JSON matches `AvailabilityLineDTO` field for field;
      per-line `need` / `need_unit` are that row's own `quantity * M` in the
      group's canonical unit; `group_*` identical across a `group_key`.
- [x] The §7 availability + aggregation oracle cases in `test_inventory_math.py`
      pass unchanged. (37 availability/aggregate cases green; file not edited.
      The 27 remaining reds are all `deduct_calc` / `_entry` — phase-4e.)
- [x] `test_recipes.py` availability fixture gains a `"salt to taste"` line;
      `?multiplier=2` asserts per-line `need` + `group_*` canonical with
      `group_unit` present and no `have` / `short` on the line; the to-taste line
      survives scaling (no `TypeError`) and reports `status="to_taste"`; a food
      cooked/edited to `quantity_base=0` -> `missing`; a title-only recipe ->
      `lines: []` with `all_available: true`. (food-to-zero shown via
      `PATCH {quantity: 0}` — `cook` lands in phase-5.)
- [x] `test_validation.py`: `availability?multiplier=` negative / `0` / `inf` /
      `nan` -> `422`.
- [~] `cd backend && uv run pytest` green — 563 passed / 27 failed. All 27 are
      the `test_inventory_math.py` R-7 locked oracles for `deduct_calc` /
      `_entry`, which `backend/CLAUDE.md` + the tracker README keep non-green
      until phase-4e. Down from 64 failed at branch point (this branch turns 37
      red -> green). Scoped `tests/test_recipes.py tests/test_validation.py` and
      the availability half of `tests/test_inventory_math.py` are fully green.
- [x] `docs/phases/phase-4.md` availability-related Work / Verification checkboxes
      ticked.

## Comments

- Branch `feat/backend-v1-phase-4d`, worktree
  `.claude/worktrees/backend-v1-phase-4d`.
- `/code-review` (Standards + Spec, since `main`): Spec axis "faithful, no
  behavioural errors". Standards axis: no hard violations. Judgement-call smells
  reviewed and deliberately kept:
  - `AvailabilityLine` re-declares `AvailabilityLineDTO` field-for-field —
    the repo's intentional schema/DTO split (matches `InventoryItemRead` etc.).
  - `status: str` (not `Literal[...]`) — stays field-for-field with the locked
    frozen DTO; no `Literal` pattern exists in `schemas/` yet.
  - `all_available` computed in the router — spec §4.2 / §5.3 explicitly assign
    it to the router ("built by the router").
  - `GroupAgg.members: list[tuple[int, float]]` and `M` param name — verbatim
    from spec §4.1.
  - `GroupAgg.display_item` unused this phase — it is a spec §4.1 field, read by
    `generate_lines` / cook in phases 5–6.
