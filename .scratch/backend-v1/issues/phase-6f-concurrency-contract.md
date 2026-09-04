# phase-6f: Concurrency contract + Phase 6 close

**What to build:** `test_concurrency.py` rewritten to assert the properties that
make a lost update *impossible* — not an interleave that `BEGIN IMMEDIATE` makes
unconstructable — plus the file-backed submit race. Closes the Phase 6 gates so
the backend is feature-complete.

**Blocked by:** `phase-6e`.

**Status:** in-review

**Files:** rewrite `backend/tests/test_concurrency.py`; edit `backend/app/main.py` / `backend/app/database.py` only if the `409` mapping needs it; `docs/phases/phase-6.md`, `docs/plan.md`.

**Spec:** `docs/spec.md` §6 (concurrency & transactions, `_to_409_if_locked_else_500`), §7 concurrency / submit-race contract + `test_concurrency.py` intent, §5.6 (submit). Read only these sections.

**Tests:** `cd backend && uv run pytest tests/test_concurrency.py`, then full `uv run pytest`.

- [x] `backend/tests/test_concurrency.py` rewritten per `spec.md` §7:
      file-backed SQLite (`tmp_path`), two independent engines / connections,
      asserting
  1. **serialization** — A begins and writes uncommitted; B's `BEGIN` blocks
     and, with `busy_timeout` lowered for the test, raises
     `OperationalError: database is locked`;
  2. **the `409` mapping** — that error, raised through an HTTP request, returns
     `409` not `500` (this is the only coverage of
     `_to_409_if_locked_else_500`);
  3. **freshness** — after A commits, B's retry reads A's committed value.
- [x] One threaded two-`cook` HTTP smoke test kept (final `quantity_base`
      correct, both `CookLog`s honest) — as a coarse check, not the guard.
- [x] A file-backed HTTP submit-race test: concurrent submits apply each checked
      line at most once.
- [x] The pre-review-pass-8 vacuous version is removed — no assertion depends on
      an interleave that `BEGIN IMMEDIATE` on every transaction makes
      unconstructable.
- [x] Submit-race oracle cases from `phase-6a` pass unchanged.
- [x] Phase 6 exit criteria in `docs/phases/phase-6.md`: R-7 gate checked and
      accepted cases unchanged; R-10 scope fence; R-6 diff-review gate (a
      non-author reviewer walked every consolidation / shortfall-uncertainty /
      submit branch of the Phase 6 diff and tests against `spec.md` §7 / §5.6);
      **backend behavior is feature-complete**.
- [x] `docs/plan.md` build-sequence status table: Phase 6 -> **Complete**.
- [x] `docs/spec.md` edited only via a paired `spec.md` + contract-test change if
      a locked oracle proved it wrong; otherwise untouched. (Untouched — no
      locked oracle was proven wrong.)
- [x] `cd backend && uv run pytest` green. (756 passed.)

## Comments

- 2026-09-04: Implemented on `test/backend-v1-phase-6f`, worktree
  `.claude/worktrees/backend-v1-phase-6f`. `test_concurrency.py` fully
  rewritten: Section A is the domain-independent serialization/freshness +
  409-mapping contract (new); Section B keeps the existing threaded two-`cook`
  smoke; Section C adds a file-backed HTTP grocery submit-race smoke. The
  locked R-7 oracles (`test_cook_contract.py` §D, `test_grocery_contract.py`
  §C, `test_inventory_math.py`) are untouched and confirmed byte-identical
  since the phase-6a lock commit `fac0edf`. R-6 diff-review gate run as a
  two-axis review (Standards + Spec sub-agents) over the full Phase 6 diff
  since `fac0edf`: 0 hard standards violations, 0 critical/major spec
  findings — see `docs/phases/phase-6.md` Exit criteria for the two accepted
  minor notes (pre-existing, from phase-6e, not reopened).
