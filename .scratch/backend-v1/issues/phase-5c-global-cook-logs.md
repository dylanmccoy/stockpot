# phase-5c: Global cook-log reads + Phase 5 close

**What to build:** `routers/cook_logs.py` at `/api/cook-logs` — a paginated
newest-first global feed and a by-id detail read, both surviving recipe deletion
— and closing the Phase 5 gates.

**Blocked by:** `phase-5b`.

**Status:** ready-for-agent

**Files:** create `backend/app/routers/cook_logs.py`, `backend/tests/test_cook_logs.py`; edit `backend/app/schemas/cook_logs.py` (add `CookLogList`), `backend/app/main.py`, `docs/phases/phase-5.md`, `docs/plan.md`.

**Spec:** `docs/spec.md` §5.4 (global `/api/cook-logs` list + by-id, pagination, survives recipe deletion). Read only this section.

**Tests:** `cd backend && uv run pytest tests/test_cook_logs.py`, then full `uv run pytest`.

- [ ] `backend/app/routers/cook_logs.py` (`prefix="/api/cook-logs"`,
      `route_class=TransactionRoute`, auth required):
  - `GET /api/cook-logs` -> `200 CookLogList {items, total, limit, offset}`;
    `limit: int = 50` (`1..200`), `offset: int = 0` (`>= 0`) -> `422` out of
    range; `total` = full count of all cook logs ignoring pagination; order
    `cooked_at DESC, id DESC`.
  - `GET /api/cook-logs/{log_id}` -> `200 CookLogRead`; `404` if absent;
    resolves after the recipe is deleted (`recipe_id` null, `recipe_title`
    snapshot stands).
- [ ] Router registered in `create_app` / `app.main`; the `test_transactions.py`
      route-class guard stays green.
- [ ] `backend/tests/test_cook_logs.py`: `GET /api/cook-logs` paginates
      newest-first across recipes (`limit` / `offset` / `total`);
      `GET /api/cook-logs/{id}` returns one; both still resolve after the recipe
      is deleted.
- [ ] Phase 5 exit criteria in `docs/phases/phase-5.md`: R-7 gate checked and
      accepted cases unchanged; R-10 scope fence; R-6 diff-review gate (a
      non-author reviewer walked every deduction / clamp-to-zero / reason branch
      of the Phase 5 diff and tests against `spec.md` §7 / §4.5 / §5.4).
- [ ] `docs/plan.md` build-sequence status table: Phase 5 -> **Complete**.
- [ ] `docs/spec.md` edited only via a paired `spec.md` + contract-test change if
      a locked oracle proved it wrong; otherwise untouched.
- [ ] `cd backend && uv run pytest` green.
