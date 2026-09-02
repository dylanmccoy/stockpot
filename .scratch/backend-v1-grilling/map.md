# Backend v1 — design grilling, shared understanding

**Effort:** `/grill-with-docs` on the recipe backend v1.
**Date:** 2026-09-01. **Branch:** `main`. **Status:** frontier empty; user confirmed.
**Type:** grilling (design interview). No implementation was performed.

Five rounds, 24 questions, 23 decisions (Q3 was superseded by Q8). This file is
the working record. Its permanent home is `docs/decisions.md` as
**Review pass 8**, per decision Q23.

---

## Notes — what the session found

Four of the decisions came from defects or divergences found by reading and
running the code, not from the user's agenda:

| # | Finding | Evidence |
|---|---|---|
| F1 | `DateTime(timezone=True)` columns come back from SQLite naive, so every Read path violates §Mechanical-defaults' `…+00:00` promise. One column was already hand-patched. | `backend/app/security.py:118-123` |
| F2 | `issue_token` reads `session_ttl_days` from the **module-global** `Settings`, so `create_app(test_settings, …)` cannot influence token lifetime. `test_auth.py` works around it by rewriting `expires_at` in the DB. | `backend/app/security.py:53`, `tests/test_auth.py:330` |
| F3 | `get_db` commits **after** `yield`. In FastAPI 0.141 / Starlette 1.6 that runs after the response is generated, so a failing commit returns **`200` with the write silently discarded** — not the `409` §6 promises, and not even a `500`. | Repro run this session (below) |
| F4 | `test_concurrency.py` as specified cannot fail. `BEGIN IMMEDIATE` on every transaction means the lost-update interleave it is meant to catch is unconstructable. | `backend/app/database.py` `on_begin`; §7 test matrix |

### F3 repro

A dependency raising post-`yield`, with a handler registered for that exception:

| `TestClient` mode | Result |
|---|---|
| `raise_server_exceptions=False` (and real uvicorn) | `200 {"ok": true}` — handler never invoked, transaction rolled back |
| `raise_server_exceptions=True` | `RuntimeError: Caught handled exception, but response already started.` |

Starlette locates the handler and then refuses it because the response is
already out. `tests/test_exception_handlers.py` misses this: it raises from
inside a route body, which is the path where handlers *do* work.

Exposure is narrowed by `autoflush=False` plus §6's "routers `flush()` when they
need a generated id" — a flush raises inside the window and converts correctly.
But that makes a documented guarantee depend on each handler happening to flush,
and it never covers `SQLITE_BUSY` at `COMMIT`.

### F3 fix, verified

A custom `APIRoute` whose handler commits after the endpoint returns was tested
and returns `409 {"detail": "conflict"}` on a commit-time failure. The wrapper
runs inside `wrap_app_handling_exceptions` and before the response is sent.
Response serialization also completes *before* the commit, so there is no
`expire_on_commit` refresh problem.

---

## Decisions

### Datetimes and timestamps

**Q1 — `UtcDateTime` TypeDecorator.**
Add one in `database.py`, apply to every datetime column, delete the ad-hoc
patch at `security.py:118-123`.
*Why:* the only fix that holds for every read path including raw-SQL ones, and
it removes existing debt rather than adding a second workaround.
*Rejected:* per-schema Pydantic field validators (misses raw-SQL paths);
accepting naive output and amending the spec.

**Q6 — Python-side timestamps everywhere.**
`default=_utcnow`, `onupdate=_utcnow`, and an explicitly bound `_utcnow()`
parameter in the §5.5 inventory upsert (which bypasses ORM `onupdate` by
construction). Amend §1's three "server default `now()`" / "`onupdate=now()`"
notes to say Python-side.
*Why:* SQLite `CURRENT_TIMESTAMP` is a naive, second-precision UTC string — it
fights the Q1 decorator and drops sub-second ordering. One clock.
*Rejected:* server defaults as §1 currently specifies.

### Auth and accounts

**Q2 — account lifecycle.**
(1) Keep the env-var first-user bootstrap; Phase 7 documents it as *the*
procedure. (2) **Add `POST /api/auth/change-password`.** (3) Accept unbounded
`sessions` growth in v1.
*Why:* without (2) a forgotten password is a `sqlite3` shell job forever. (3) a
household generates a few rows a month.
*Rejected:* session reaping on login or by sweep.

**Q7 — `change-password` contract.**
`403 {"detail": "incorrect password"}` on a wrong old password. Revoke the
user's other sessions. Phase 2 owns it (reopened — it is uncommitted).
*Why:* the token is valid and the *action* is refused; `401` would wrongly tell
the client to re-login. Revocation is what makes the endpoint worth having.
*Rejected:* `401`; leaving other sessions alive; deferring to Phase 7.

**Q12 — rotate the caller's token too.**
Delete every session for the user including the caller's, `issue_token` a fresh
one, return `200 TokenResponse` — the same shape `login` returns.
*Why:* makes revocation one unconditional `DELETE WHERE user_id = me` with no
`AND id != current` special case; a full-window reset is what someone changing a
password actually wants.
*Rejected:* reusing the caller's row (a session spanning a credential change).

**Q9 — `issue_token(db, user, settings)`.**
Pass settings in; both callers are in `routers/auth.py`, which already has it
injected. Fixes F2.
*Why:* removes the last module-global config read from a request path and makes
`issue_token` a pure function of its arguments.
*Rejected:* reading `request.app.state` inside `issue_token`; leaving it.

**Q14 — leave the two import-time module globals alone.**
`database.py:51` (`engine`) and `main.py:67` (`app`) stay.
*Why:* they are the `uvicorn app.main:app` entrypoint documented in three
places. SQLAlchemy engines are lazy, so the test-suite side effect is a file
that never gets touched. Revisit only if a test is observed writing `recipe.db`.
*Rejected:* `--factory` style entrypoint.

**Q22 — `ge=0` on `session_ttl_days`; leave `cors_origins` alone.**
*Why:* zero is meaningful (instantly-expired — the clean way to test the expiry
branch now that Q9 makes it injectable); negative is pure misconfiguration.
`cors_origins`' localhost:5173 default is inert in v1 and Phase 7 owns
explaining it.
*Rejected:* `ge=1` (would close the door Q9 just opened); defaulting
`cors_origins` to `[]`.

### Transactions

**Q13 — a `TransactionRoute(APIRoute)` subclass owns the commit.**
It commits after the endpoint returns but before the response is built. Fixes
F3. Add a test that raises at commit specifically.
*Why:* the only option where a client is never told a write succeeded when it
did not. Silent data loss is the one failure mode a household recipe box cannot
absorb.
*Rejected:* mandating a trailing `flush()` in every mutating handler (catches
constraint violations only, not commit-time locks); accepting it and narrowing
§6.

**Q24 — location, wiring, and the guard test.**
`TransactionRoute` lives in `database.py` beside `get_db`. `get_db` stashes
`request.state.db`; the route class reads `getattr(request.state, "db", None)`
and no-ops when absent, so `/api/health` needs no special case.
**Add a guard test** iterating `app.routes` asserting every `/api` route with a
DB dependency is a `TransactionRoute`.
*Why:* `route_class` is a property of the `APIRouter` a route is *declared* on
and `include_router` cannot apply it retroactively. Phases 4–6 each add a
router; a forgotten `route_class=` silently reverts that router to the F3 bug
with no test failing. The guard test is the only mechanism that catches it.
*Rejected:* `main.py` as the home (routers cannot import `main` — cycle);
relying on a `make_router()` helper alone.

**Q17 — rewrite §6's transaction-ownership paragraph.**
Name the route class as owner. `get_db` keeps `rollback()`-on-exception and
`close()`. `flush()` shrinks back to one job: "call it when you need a generated
id." State explicitly that a commit-time `IntegrityError` or write-lock now
converts to `409` like an in-handler one. §3.2 and §3.3 need matching edits.
*Unchanged:* a route raising `HTTPException(404)` still rolls back, so
`get_current_user`'s `last_used_at` bump is still lost on an error response.

**Q8 — rewrite `test_concurrency.py`'s contract.** *(supersedes Q3)*
Assert serialization + freshness + the `409` mapping: A begins and writes
uncommitted; B's begin blocks and, with `busy_timeout` lowered for the test,
raises `OperationalError: database is locked`; assert the global handler maps it
to `409`, not `500`; A commits; B retries and reads A's committed value. Keep
one threaded two-`cook` HTTP test as a smoke check.
*Why:* fixes F4 — the test must assert the property that *prevents* the race,
since `BEGIN IMMEDIATE` makes the race itself unconstructable. Also exercises an
error-translation path §0 promises and nothing currently tests.
*Rejected:* the raw two-`Session` lost-update interleave I recommended in Q3
(impossible); threaded-HTTP only (flaky, gets skipped); leaving it.

### Recipes and schemas

**Q4 — normalize `unit` on both input paths: lowercase + strip one trailing `.`, no singularization.**
*Why:* the only raw consumer of `recipe_ingredients.unit` is `RecipeRead`; every
math path (`bucket_of`, `add_quantities`, `to_base`) already calls
`normalize_unit_token`, which lowercases, strips, **and** singularizes. So
singularizing on write changes exactly one displayed string, while costing a
locked R-7 oracle (§2.3 "`cups` stays `cups`", §7 `test_ingredient_parse` row)
and reading wrong (`2 cup flour`, `3 clove garlic`). Casing and punctuation are
cosmetic and cannot damage a word.
*Rejected:* singularizing on write; normalizing neither path; documenting the
asymmetry.

**Q5 — zero-content recipes are permanently legal.**
Only `title` is required; `ingredients` and `steps` both default to `[]`. Add an
explicit §5.2 line.
*Why:* a title-only stub is a legitimate capture-now-fill-later flow, and every
downstream case is already total (availability `lines: []` / `all_available:
true`; grocery emits nothing; cook writes `deductions: []`). The spec line stops
a later reviewer "fixing" it.
*Rejected:* a minimum-content rule.

**Q11 — `ConfigDict(extra="forbid")` on `RecipeIngredientIn` only.**
*Why:* it is the only schema where a dropped key produces a *successful wrong
write* rather than an error — `{"item": "flour", "qty": 500}` returns `201` and
silently stores a to-taste ingredient, because to-taste is a legitimate value
for the field that goes missing.
*Rejected:* `extra="forbid"` on every request schema (touches every Phase 3–6
schema; wait for evidence); leaving it.

**Q10 — keep canonical-unit-only responses (#P5), and record the v2 note.**
*Why:* one representation is what makes the netting, consolidation, and
deduction math auditable, and all the R-7 oracles are expressed in canonical
units. Choosing *which* display preference wins is a real design question, not a
tweak.
*Done this session:* `docs/features.md` gained a row in the "Additional deferred
features" table and a `### Display-unit conversion on output` subsection
covering the user-visible consequence (`2 lb` in → `453.592 g` on the grocery
list), the `units.from_base` hook, and the frontend-effort trigger.

### Operations and documentation

**Q15 — document a backup procedure in Phase 7.**
`sqlite3 recipe.db ".backup 'recipe-$(date +%F).db'"` (safe on a live DB, unlike
`cp`) plus the restore step. Leave the Alembic trigger where `features.md:320`
puts it.
*Why:* schema changes are `rm backend/recipe.db`, Alembic is deferred to the
first change *after* v1, and nothing currently tells an operator to take a copy
— so the moment data becomes valuable and the moment a tool exists to protect it
are separated by an unbounded gap. Grep found exactly one occurrence of "backup"
in the whole repo, an aside about Postgres.
*Rejected:* pulling Alembic into v1 (contradicts a deliberate, well-argued
deferral); a `GET /api/export` endpoint (new v1 surface for something `sqlite3`
does better); doing nothing.

**Q18 — one "Operating the server" section in `README.md`.**
Ordered runbooks: first-user bootstrap (open window → register → stop → restart
closed), schema reset (snapshot → `rm recipe.db` → restart), restore. Phase 7's
existing checklist items point at it instead of each describing a fragment.
*Why:* all three are the same activity — a human at a terminal, server stopped,
doing something irreversible — and the ordering that matters is exactly what
gets lost when they are scattered across three documents.

**Q19 — commit `docs/frontend/`.**
*Why:* `plan.md`'s document map has a row for it and `phase-7.md` is instructed
to link to it as the frontend's planning home; not committing it leaves two
documents pointing at nothing. The scope fence already handles the risk in
prose, and untracked planning docs rot.
*Rejected:* leaving it untracked or moving it to a branch.

### Process

**Q16 — commit the working tree as four separate PRs, before any decision here is implemented.**
Order: tooling (`.claude/`, `.agents/`, `skills-lock.json`, `CLAUDE.md`) → docs
(`docs/agents/`, `docs/frontend/`, existing doc edits) → Phase 2 backend as-is →
this session's output (`CONTEXT.md`, the `features.md` note, this file).
*Why:* the tree currently mixes four unrelated concerns across 13 modified and 8
untracked paths, and five decisions here reopen Phase 2 files. Landing them on
top produces one undifferentiated blob, and `plan.md`'s R-6 gate requires a
non-author reviewer to read it. It also makes Phase 2's status correspond to
something in git history for the first time.

**Q20 — one spec-edit PR, then one Phase 2 hardening PR, then Phase 3.**
*Why:* `plan.md` requires spec edits before the owning phase implements. The
five Phase 2 items are all infrastructure in the same four files and want one
R-6 reviewer pass, not five. One spec PR is *more* reviewable than five
scattered ones because the decisions interlock — Q1 and Q6 are one paragraph,
Q13 and Q17 are one section.
*Rejected:* per-phase spec edits; folding the Phase 2 reopen into Phase 3 (puts
auth infrastructure and recipe modelling under one review).

**Q21 — no new R-7 contract-test gate for Phase 3; add explicit §7 rows instead.**
Rows to write: `{"item": "flour", "qty": 500}` → `422` naming `qty`;
`{"unit": "Tbsp."}` stored as `tbsp`; title-only `POST` → `201` with
`ingredients: []`.
*Why:* the gate exists to stop implementation and validation sharing an
interpretation error in *arithmetic*. Q4/Q5/Q11 are single-branch rules where a
spec sentence and a test row are the same statement. Expanding the gate list has
real process cost and buys nothing here.

**Q23 — one `decisions.md` entry; revert Phase 2 to "In progress".**
Record as `## Review pass 8 — design grilling (2026-09-01)` with a numbered
sub-item per decision, matching how passes 2–7 are already recorded. Add the
five hardening items to `phase-2.md`'s checklist.
*Why:* the decisions interlock, so eleven scattered entries lose that. Phase 2
is not Complete — nothing is in git — and "In progress" leaves `plan.md`'s
"eight phases, numbered 0–7" sentence alone. ("Phase 2.1" was shorthand for the
PR, not a proposed phase.) Mark Complete when the hardening lands.

---

## Change list

### `backend/app/` — Phase 2 reopen

| File | Change |
|---|---|
| `database.py` | Add `UtcDateTime(TypeDecorator)`. `get_db` stops committing; stashes `request.state.db`; keeps rollback + close. Add `TransactionRoute(APIRoute)`. |
| `models.py` | `UtcDateTime` on every datetime column; `default=_utcnow`, `onupdate=_utcnow`. |
| `security.py` | Delete the naive-datetime patch (L118-123). `issue_token(db, user, settings)`. |
| `routers/auth.py` | Pass settings to `issue_token`. Add `POST /api/auth/change-password`. `route_class=TransactionRoute`. |
| `routers/recipes.py` | `route_class=TransactionRoute`. |
| `config.py` | `session_ttl_days: int = Field(30, ge=0)`. |
| `tests/` | change-password cases; a commit-time-failure test; the `TransactionRoute` guard test. |

### `backend/app/` — Phase 3

| File | Change |
|---|---|
| `schemas/recipe.py` | `ConfigDict(extra="forbid")` on `RecipeIngredientIn`. |
| `routers/recipes.py` | Normalize `unit` on the object branch of the §5.2 build loop (lowercase + strip one trailing `.`). |

### Later phases

- **Phase 6** — rewrite `test_concurrency.py` per Q8.
- **Phase 7** — `README.md` "Operating the server" runbook (Q15, Q18); Phase 7
  checklist items point at it.

### `docs/`

| File | Change |
|---|---|
| `spec.md` §1 | Timestamp wording server→Python (×3); `recipe_ingredients.unit` note covers both paths. |
| `spec.md` §3.2 | `UtcDateTime`; `get_db` no longer commits; `TransactionRoute`. |
| `spec.md` §3.3 | Commit-time errors convert to `409`. |
| `spec.md` §3.4 | `issue_token` signature. |
| `spec.md` §5.1 | `POST /api/auth/change-password`. |
| `spec.md` §5.2 | Unit normalization on the object branch; zero-content legality; `extra="forbid"`. |
| `spec.md` §5.5 | Explicitly bound `_utcnow()` in the upsert. |
| `spec.md` §6 | Transaction-ownership rewrite (Q17). |
| `spec.md` §7 | New `test_auth.py` rows; new `test_recipes.py` rows; `test_concurrency.py` row rewritten. |
| `plan.md` | Phase 2 → In progress. |
| `phases/phase-2.md` | Five hardening checklist items. |
| `phases/phase-7.md` | Backup task; point at the README runbook. |
| `decisions.md` | Review pass 8. |
| `features.md` | ✅ done this session (Q10). |
| `CONTEXT.md` | ✅ created this session. |

---

## Sequence

1. Commit tooling.
2. Commit docs (includes `docs/frontend/`).
3. Commit Phase 2 backend as-is, suite green.
4. Commit this session's output (`CONTEXT.md`, `features.md` note, this file).
5. **Spec-edit PR** — all 23 decisions, plus the Review pass 8 entry.
6. **Phase 2 hardening PR** — Q1, Q6, Q7, Q9, Q12, Q13, Q22, Q24. R-6 review.
   Mark Phase 2 Complete.
7. **Phase 3** — Q4, Q5, Q11 land with the existing phase work.

---

## Fog — deliberately not resolved

- **D1** (open-vocabulary singularization for ingredient names) and **D2**
  (multi-line ingredient paste) are untouched. Neither was opened this session.
- **Alembic** stays deferred to the first schema change after v1
  (`features.md:320`). Q15 mitigates the data-loss window with documentation
  rather than moving the trigger.
- **No linter** is configured. Raised as low-priority process, not asked.
- **No ADR was written.** Nothing here clears hard-to-reverse **and** surprising
  **and** a real trade-off. Q13 comes closest; it is a bug fix with one sensible
  answer, so it belongs in `decisions.md`.

## Domain model

`CONTEXT.md` was created at the repo root (glossary only, no implementation
detail). It pins the vocabulary Q4 forced into the open — three distinct things
in this codebase were all called "unit":

**Author's unit** (verbatim, display only) · **Canonical unit** (`g`/`ml`/`unit`
or the opaque token; what is stored and what every API quantity outside a recipe
body reports) · **Display unit** (a per-inventory-row rendering preference,
never a source of truth) · **Unit bucket** (the compatibility class) ·
**Opaque unit** (deliberately unconvertible: `can`, `clove`, `bunch`).

Grow it as later work settles terms.
