# phase-5a: Cook contract-test lock (R-7)

**What to build:** A locked, independently-reviewed black-box test slice for
cooking, audit-log serialization, and the cook race — authored from
`docs/spec.md` §4.5 / §5.4 / §6 / §7 only, in a fresh context, before Phase 5
production code.

**Blocked by:** `phase-4e` (Phase 4 complete).

**Status:** in-review

**Files:** edit `backend/tests/test_inventory_math.py` and/or create `backend/tests/test_cook_contract.py`; `docs/phases/phase-5.md`. Authored black-box from the spec in a fresh context — no production code.

**Spec:** `docs/spec.md` §4.5 (deduction), §5.4 (cook + made-history, `CookDeductionRead` shape, N7), §6 (cook race), §7 cook + audit-log contract rows. Read only these sections.

**Tests:** n/a — this suite is locked and is **not** expected to pass until `phase-5b`.

- [x] §7 cook + audit-log contract cases authored black-box from `spec.md` into
      the appropriate module(s) (`test_inventory_math.py` additions and/or a cook
      contract test): the deduction outcomes for `deduct=true`, the
      `CookDeductionRead` JSON shape (all 11 keys, `reason` in the 5-value
      `Literal`, `null` only where the §5.4 table permits), and a stored entry
      with an extra/unknown key or an unlisted `reason` -> `500` on read (N7).
      *(new file `backend/tests/test_cook_contract.py`, section A + B + C;
      `test_inventory_math.py` untouched — the deferred `CookDeductionRead`
      round-trip is authored here instead.)*
- [x] The cook-race contract specified: a file-backed HTTP two-`cook` race does
      not lose an update; concurrent writers serialize (second `BEGIN` blocks;
      with `busy_timeout` lowered -> `database is locked` -> `409`, not `500`).
      *(section D: serialization + freshness at engine level, the 409-not-500
      HTTP mapping, and a threaded two-`cook` no-lost-update smoke.)*
- [x] Reviewed and accepted as **locked** per
      [`docs/plan.md` §Independent contract-test gate](../../../docs/plan.md);
      the acceptance is recorded.
      *(fresh-context `/code-review` Standards + Spec axes on the diff; Spec axis
      verdict "faithful to spec, no wrong expected values"; nits actioned —
      `R()`/`S()` shorthand, named wait bounds + lower-bound assertion, fixture
      split for `raise_server_exceptions`, `cooked_by`/full `CookLogRead` shape
      locked. Acceptance recorded here and in the commit + `phase-5.md` gate.)*
- [x] `docs/phases/phase-5.md` R-7 gate checkbox ticked.
- [x] Not expected to pass until `phase-5b` — fails on collection
      (`app.schemas.cook_logs`). Rest of the suite unchanged: 590 passed.

## Comments

- Branch: `test/backend-v1-phase-5a` (off `main`).
- Worktree: `.claude/worktrees/backend-v1-phase-5a`.
- One test file added: `backend/tests/test_cook_contract.py` (~970 lines,
  27 tests + oracle helpers). No production code touched.
- Locked-oracle behaviour matches the sibling `phase-4a`: the file does not
  collect until its owning implementation ticket (`phase-5b`) lands
  `app.schemas.cook_logs` + the cook route/model. `cd backend && uv run pytest`
  is therefore red on this branch by design (`README.md`: the three R-7
  oracle-lock tickets are the exception to the green-suite rule).
