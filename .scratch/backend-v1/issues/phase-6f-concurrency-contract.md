# phase-6f: Concurrency contract + Phase 6 close

**What to build:** `test_concurrency.py` rewritten to assert the properties that
make a lost update *impossible* — not an interleave that `BEGIN IMMEDIATE` makes
unconstructable — plus the file-backed submit race. Closes the Phase 6 gates so
the backend is feature-complete.

**Blocked by:** `phase-6e`.

**Status:** ready-for-agent

**Files:** rewrite `backend/tests/test_concurrency.py`; edit `backend/app/main.py` / `backend/app/database.py` only if the `409` mapping needs it; `docs/phases/phase-6.md`, `docs/plan.md`.

**Spec:** `docs/spec.md` §6 (concurrency & transactions, `_to_409_if_locked_else_500`), §7 concurrency / submit-race contract + `test_concurrency.py` intent, §5.6 (submit). Read only these sections.

**Tests:** `cd backend && uv run pytest tests/test_concurrency.py`, then full `uv run pytest`.

- [ ] `backend/tests/test_concurrency.py` rewritten per `spec.md` §7:
      file-backed SQLite (`tmp_path`), two independent engines / connections,
      asserting
  1. **serialization** — A begins and writes uncommitted; B's `BEGIN` blocks
     and, with `busy_timeout` lowered for the test, raises
     `OperationalError: database is locked`;
  2. **the `409` mapping** — that error, raised through an HTTP request, returns
     `409` not `500` (this is the only coverage of
     `_to_409_if_locked_else_500`);
  3. **freshness** — after A commits, B's retry reads A's committed value.
- [ ] One threaded two-`cook` HTTP smoke test kept (final `quantity_base`
      correct, both `CookLog`s honest) — as a coarse check, not the guard.
- [ ] A file-backed HTTP submit-race test: concurrent submits apply each checked
      line at most once.
- [ ] The pre-review-pass-8 vacuous version is removed — no assertion depends on
      an interleave that `BEGIN IMMEDIATE` on every transaction makes
      unconstructable.
- [ ] Submit-race oracle cases from `phase-6a` pass unchanged.
- [ ] Phase 6 exit criteria in `docs/phases/phase-6.md`: R-7 gate checked and
      accepted cases unchanged; R-10 scope fence; R-6 diff-review gate (a
      non-author reviewer walked every consolidation / shortfall-uncertainty /
      submit branch of the Phase 6 diff and tests against `spec.md` §7 / §5.6);
      **backend behavior is feature-complete**.
- [ ] `docs/plan.md` build-sequence status table: Phase 6 -> **Complete**.
- [ ] `docs/spec.md` edited only via a paired `spec.md` + contract-test change if
      a locked oracle proved it wrong; otherwise untouched.
- [ ] `cd backend && uv run pytest` green.
