# phase-5b: Cook + per-recipe history

**What to build:** `POST /api/recipes/{id}/cook` records a `CookLog` and, when
`deduct=true`, draws down inventory inside one transaction;
`GET /api/recipes/{id}/cook-logs` lists that recipe's history newest-first.

**Blocked by:** `phase-5a`.

**Status:** ready-for-agent

- [ ] `backend/recipe.db` deleted (schema expansion).
- [ ] `CookLog` model per §1: `recipe_id` FK `ON DELETE SET NULL`
      `passive_deletes=True`, `recipe_title` snapshot, `multiplier` (`>0`, finite,
      default `1`), `deducted` (default `true`), `cooked_at`, `cooked_by_id`
      nullable with no cascade, `deductions` raw `JSON list[dict]`.
- [ ] `backend/app/schemas/cook_logs.py` with `CookDeductionRead`
      (`model_config = ConfigDict(extra="forbid")`, 11 fields, `reason` a 5-value
      `Literal`) and `CookLogRead` (`deductions: list[CookDeductionRead]`);
      re-exported from `app.schemas`.
- [ ] `POST /api/recipes/{id}/cook` -> `201 CookLogRead`: body
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
- [ ] `GET /api/recipes/{id}/cook-logs` -> `200 list[CookLogRead]`,
      `order_by(cooked_at DESC, id DESC)`, unpaginated; `404` if the recipe is
      absent.
- [ ] The cook router uses `route_class=TransactionRoute`; the
      `test_transactions.py` route-class guard stays green.
- [ ] `test_recipes.py`: `/cook` writes a `CookLog` and mutates inventory (clamp;
      incompatible bucket); the to-taste line yields a `"to taste"` deduction
      entry that is never applied; every deduction entry validates against
      `CookDeductionRead` — all 11 keys, `reason` in the allowed `Literal`, `null`
      only where the §5.4 table permits; a stored entry with an extra/unknown key
      or an unlisted `reason` -> `500` on read; `"ok"`, `"clamped to 0"`,
      `"not in inventory"`, `"have uncertain (incompatible unit)"`, `"to taste"`
      each exercised at least once; `cook {deduct:false}` leaves inventory
      untouched but still writes a `CookLog`; `GET .../cook-logs` newest-first
      across both modes.
- [ ] A file-backed HTTP two-`cook` race smoke test (per the §7
      `test_concurrency.py` intent): concurrent cooks do not lose an update; the
      `/cook` fixture recipe carries a `"salt to taste"` line asserted to scale
      with `multiplier` without `TypeError`.
- [ ] Cook + audit-log oracle cases from `phase-5a` pass unchanged.
- [ ] `cd backend && uv run pytest` green.
- [ ] `docs/phases/phase-5.md` cook / schema / per-recipe-history Work and
      Verification checkboxes ticked.
