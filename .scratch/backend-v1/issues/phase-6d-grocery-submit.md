# phase-6d: Grocery submit

**What to build:** `POST /api/grocery/{id}/submit` applies every checked,
unfrozen, quantified line into inventory once, inside one transaction, and
freezes it — forward-only, with no status change.

**Blocked by:** `phase-6c`.

**Status:** in-review

**Files:** edit `backend/app/routers/grocery.py` (add `/submit`), `backend/app/schemas/grocery.py`, `backend/tests/test_grocery.py`.

**Spec:** `docs/spec.md` §5.6 (submit — forward-only, freeze, no status change), §5.5 (`add_to_inventory_calc` + `ON CONFLICT` upsert, reused), §7 submit contract rows, §6 (`409` on lock). Read only these sections.

**Tests:** `cd backend && uv run pytest tests/test_grocery.py`, then full `uv run pytest`.

- [x] `POST /api/grocery/{id}/submit` -> `200 GroceryListRead`: `404` if the list
      is absent; `409` if `list.status != "active"`; inside the request's single
      `BEGIN IMMEDIATE` transaction, for each line skip unless
      `line.checked and not line.added_to_inventory and line.quantity is not None`,
      else `delta = add_to_inventory_calc(normalize_name(line.item), line.item,
      line.quantity, line.unit)` + the §5.5 `ON CONFLICT` upsert, then set
      `line.applied_quantity, line.applied_unit = delta.canonical_added.amount,
      delta.canonical_added.unit`, `line.added_to_inventory = True`,
      `line.submitted_at = _utcnow()`; `list.status` is **not** changed.
- [x] Forward-only: already-applied lines are skipped, so a re-submit picks up
      only newly-checked lines; nothing eligible -> `200`, list unchanged
      (explicit no-op); a checked `nettable=false` line **with** a real
      `quantity` is added; a checked `quantity=null` line is silently skipped;
      `IntegrityError` / lock timeout -> `409`, whole transaction rolled back.
- [x] Submit oracle cases from `phase-6a` pass unchanged.
- [x] `test_grocery.py`: edit a checked line then `submit` -> inventory reflects
      the edited value (`0.5 kg`, not `500 kg`); `submit` -> inventory up + line
      frozen (`added_to_inventory`, canonical `applied_quantity`); `PATCH` /
      `DELETE` a frozen line -> `409`; uncheck before submit -> no-op; `submit`
      does not archive — check a further line and re-submit picks up only it;
      `submit` with nothing checked -> `200` no-op; sequential double-submit
      idempotency.
- [ ] `cd backend && uv run pytest` green. 1 pre-existing failure remains —
      `test_grocery_contract.py::test_submit_on_a_non_active_list_is_409` needs
      `POST /api/grocery/{id}/archive` (`404` today) to archive the list before
      exercising the non-active-submit `409`; that endpoint is `phase-6e`'s per
      `phase-6a`'s own comment ("`phase-6d` (submit) / `phase-6e` (archive)
      close the rest"). Not a regression: was already failing before this
      ticket, for the same reason. Full suite: 748 passed, 1 failed.
- [x] `docs/phases/phase-6.md` submit checkbox ticked.

## Comments

- Implemented on `feat/backend-v1-phase-6d` in worktree
  `.claude/worktrees/backend-v1-phase-6d`. Reviewed via `/code-review since
  main` (Standards + Spec axes).
  - Standards: no hard violations. One judgement-call flagged — the new
    `submit`'s `sqlite_insert(...).on_conflict_do_update(...)` upsert
    duplicates `routers/inventory.py`'s `add_inventory` shape line-for-line.
    Deliberately not extracted here: this ticket's **Files:** field scopes out
    `inventory.py`, and `services/inventory_math.py`'s stated role is a pure
    calc layer, not DB-statement building, so the right home for a shared
    helper is a design call, not a mechanical DRY fix. Left as a follow-up
    suggestion rather than actioned in this diff.
  - Spec: no findings. Forward-only skip, canonical `applied_quantity`/
    `applied_unit`, `list.status` untouched, `404`/`409` codes, and the
    §5.5-reused upsert shape all confirmed against `docs/spec.md` verbatim.
    The one still-failing contract test was confirmed correctly out of scope
    (needs `phase-6e`'s archive).
