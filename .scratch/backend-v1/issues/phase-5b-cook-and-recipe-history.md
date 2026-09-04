# phase-5b: Cook + per-recipe history

**What to build:** `POST /api/recipes/{id}/cook` records a `CookLog` and, when
`deduct=true`, draws down inventory inside one transaction;
`GET /api/recipes/{id}/cook-logs` lists that recipe's history newest-first.

**Blocked by:** `phase-5a`.

**Status:** in-review

**Files:** create `backend/app/schemas/cook_logs.py`; edit `backend/app/models.py` (add `CookLog`), `backend/app/schemas/__init__.py`, `backend/app/routers/recipes.py` (add `/cook`, `/cook-logs`), `backend/app/main.py`, `backend/tests/test_recipes.py`, `backend/tests/test_concurrency.py`.

**Spec:** `docs/spec.md` §1 "cook_logs" (model), §5.4 (cook endpoint, per-recipe history, `CookDeductionRead`/`CookLogRead`), §4.5 (`deduct_calc` consumed here), §6 (transaction / `409`). Read only these sections.

**Tests:** `cd backend && uv run pytest tests/test_recipes.py tests/test_inventory_math.py`, then full `uv run pytest`.

- [x] `backend/recipe.db` deleted (schema expansion).
- [x] `CookLog` model per §1: `recipe_id` FK `ON DELETE SET NULL`
      `passive_deletes=True`, `recipe_title` snapshot, `multiplier` (`>0`, finite,
      default `1`), `deducted` (default `true`), `cooked_at`, `cooked_by_id`
      nullable with no cascade, `deductions` raw `JSON list[dict]`.
      *(`passive_deletes` sits on the new `Recipe.cook_logs` back-ref; `>0`/finite
      also enforced by `CheckConstraint`, mirroring `inventory_items`.)*
- [x] `backend/app/schemas/cook_logs.py` with `CookDeductionRead`
      (`model_config = ConfigDict(extra="forbid")`, 11 fields, `reason` a 5-value
      `Literal`) and `CookLogRead` (`deductions: list[CookDeductionRead]`);
      re-exported from `app.schemas`. *(also `CookRequest` here.)*
- [x] `POST /api/recipes/{id}/cook` -> `201 CookLogRead`: body
      `CookRequest {multiplier: float > 0 allow_inf_nan=False default 1,
      deduct: bool default true}`; `404` if the recipe is absent; build
      `CookLog(recipe_id, recipe_title=recipe.title, multiplier, deducted=deduct,
      cooked_by=user)`; `deduct=false` -> save with `deductions=[]` and return;
      `deduct=true` -> build `ReqLine` with
      `quantity = None if ing.quantity is None else ing.quantity * multiplier`,
      call `deduct_calc`, then **within the request's single `BEGIN IMMEDIATE`
      transaction** apply every `RowDeduction` via a Core
      `UPDATE inventory_items SET quantity_base=?, updated_at=? WHERE id=?`
      binding `_utcnow()` (a Core `UPDATE` does not fire the ORM `onupdate`), set
      `log.deductions = proposal.log_entries`, save;
      `IntegrityError` / lock timeout -> `409` (global handler), whole
      transaction rolled back.
- [x] `GET /api/recipes/{id}/cook-logs` -> `200 list[CookLogRead]`,
      `order_by(cooked_at DESC, id DESC)`, unpaginated; `404` if the recipe is
      absent.
- [x] The cook router uses `route_class=TransactionRoute` (inherited from the
      `recipes` router); the `test_transactions.py` route-class guard stays green.
- [x] `test_recipes.py`: `/cook` writes a `CookLog` and mutates inventory (clamp;
      incompatible bucket); the to-taste line yields a `"to taste"` deduction
      entry that is never applied; every deduction entry validates against
      `CookDeductionRead` — all 11 keys, `reason` in the allowed `Literal`, `null`
      only where the §5.4 table permits; a stored entry with an extra/unknown key
      or an unlisted `reason` -> `500` on read; `"ok"`, `"clamped to 0"`,
      `"not in inventory"`, `"have uncertain (incompatible unit)"`, `"to taste"`
      each exercised at least once; `cook {deduct:false}` leaves inventory
      untouched but still writes a `CookLog`; `GET .../cook-logs` newest-first
      across both modes.
- [x] A file-backed HTTP two-`cook` race smoke test (per the §7
      `test_concurrency.py` intent): concurrent cooks do not lose an update; the
      `/cook` fixture recipe carries a `"salt to taste"` line asserted to scale
      with `multiplier` without `TypeError`. *(new `backend/tests/test_concurrency.py`.)*
- [x] Cook + audit-log oracle cases from `phase-5a` pass unchanged
      (`test_cook_contract.py`, 53 cases, no expected value altered).
- [x] `cd backend && uv run pytest` green — **655 passed**.
- [x] `docs/phases/phase-5.md` cook / schema / per-recipe-history Work and
      Verification checkboxes ticked (global-routes + Phase-5 exit criteria left
      for `phase-5c`).

## Comments

- Branch: `feat/backend-v1-phase-5b` (off `main`).
- Worktree: `.claude/worktrees/backend-v1-phase-5b`.
- `backend/app/main.py` needed no change: `/cook` + `/cook-logs` hang off the
  already-registered `recipes` router; the global `/api/cook-logs` router is
  `phase-5c`.
- `recipe_availability` was refactored (not just added to): the shared
  `ReqLine` / `StockRow` build is now `_req_lines()` / `_stock_rows()`, consumed
  by both availability and cook. Behaviour-neutral; the alternative was
  duplicating ~15 lines into the cook handler.
- `/code-review` (Standards + Spec, parallel sub-agents vs `main`): no hard
  standards violations, no wrong spec values. Actioned: (1) `test_concurrency.py`
  fixture type annotation corrected (`FastAPI`, not `Engine`); (2) the N7
  500-on-read test parametrized over both the stray-key and the unlisted-`reason`
  mutation. Deliberately kept: the availability refactor (above); the small
  reason/key-list duplication in `test_recipes.py` (independent re-derivation of
  the oracle, a judgement call).
