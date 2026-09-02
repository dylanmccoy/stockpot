# Phase 2 — Authentication and App Factory

## Goal

Introduce app-local database wiring, the request transaction policy, opaque
sessions, registration/login, and authentication gating.

## Specification

- [`spec.md` §1 — users and sessions](../spec.md#1-data-model--backendappmodelspy)
- [`spec.md` §3 — app infrastructure](../spec.md#3-app-infrastructure)
- [`spec.md` §3.1 — settings](../spec.md#31-backendappconfigpy)
- [`spec.md` §3.2 — `UtcDateTime`, `get_db`, `TransactionRoute`](../spec.md#32-backendappdatabasepy)
- [`spec.md` §5.1 — auth API](../spec.md#51-auth--routersauthpy-prefix-apiauth)
- [`spec.md` §6 — concurrency and transactions](../spec.md#6-concurrency--transactions)
- Auth and concurrency rows in [`spec.md` §7](../spec.md#7-acceptance-criteria--test-matrix)

## Work

- [x] Add settings for session lifetime and controlled registration.
- [x] Implement `make_engine`, `make_session_factory`, request-aware `get_db`,
      and `SessionDep`; retain one default engine and no global `SessionLocal`.
- [x] Enable foreign keys, busy timeout, and `BEGIN IMMEDIATE` listeners.
- [x] Implement `create_app(settings, engine)`, app state, health route, and the
      global 409 exception translations.
- [x] Add `User` and `Session`, including case-insensitive username uniqueness.
- [x] Add password hashing, token creation, `get_current_user`, and five explicit
      authentication failure paths.
- [x] Replace the flat `schemas.py` module with a `schemas/` package containing
      `common.py`, `auth.py`, and an `__init__.py` that re-exports their public
      schemas; later phases add `recipe.py`, `inventory.py`, and `grocery.py`.
- [x] Add auth schemas and register/login/logout/me routes.
- [x] Gate recipe routes.
- [x] **Before any route work (R-8),** a reviewer who does not write this phase's
      production code replaces `backend/tests/conftest.py`: delete the
      `dependency_overrides` seam; build the app via
      `create_app(test_settings, test_engine)` with a `make_engine`-built in-memory
      `StaticPool` engine that carries the same `connect` / `begin` listeners as
      production; add `client` / `user` / `auth_client` fixtures. Get one real test
      green through it before the implementation pass extends it per phase.
- [x] Add `test_auth.py` and migrate existing recipe tests to `auth_client`.

### Hardening (review pass 8, reopened 2026-09-01)

The first pass shipped in PR #20. Review pass 8 found three defects and one
divergence in it; the spec sections above were amended before this work
(`decisions.md` §Review pass 8). All five items are infrastructure in the same
four modules and land as one reviewable diff.

- [x] Add `UtcDateTime` to `database.py` and apply it to **every** datetime
      column in `models.py`; delete the ad-hoc naive-datetime normalization in
      `security.py`'s expiry comparison. Give every timestamp a Python-side
      `default=_utcnow` and, where §1 says so, `onupdate=_utcnow`.
- [x] Move the commit out of `get_db` into `TransactionRoute` (§3.2/§6):
      `get_db` stashes `request.state.db`, keeps rollback-on-exception and
      close, and no longer commits after `yield`. Build **every**
      database-touching router with `route_class=TransactionRoute`.
- [x] Change `issue_token` to `issue_token(db, user, settings)` and pass
      settings from both call sites in `routers/auth.py`.
- [x] Constrain `session_ttl_days` to `Field(30, ge=0)` in `config.py`.
- [x] Add `POST /api/auth/change-password` (§5.1): `403` on a wrong current
      password, delete every session for the user including the caller's, issue
      a fresh token, return `200 TokenResponse`.

## Verification

- [x] Registration defaults off and requires the configured code when enabled.
- [x] `last_used_at` persists as part of the request transaction.
- [x] Missing, malformed, wrong-scheme, unknown, and expired tokens return 401.
- [x] A listener-parity test on the fixture engine passes (R-8): `PRAGMA
      foreign_keys` returns `1`, and while a transaction holds the write lock a
      second connection's write blocks and then times out under `busy_timeout` —
      so a missing `connect` / `begin` listener fails a test instead of silently
      disabling the lock.
- [x] `cd backend && uv run pytest` passes.

### Hardening verification

- [x] Every response datetime carries an explicit UTC offset — `UserRead` and
      `RecipeRead` both, on create and on re-read. **The `created_at ==
      updated_at` / `PUT` advances `updated_at` half is deferred to Phase 3**,
      which is where `Recipe` gains an `updated_at` column (`spec.md` §1). No
      table in the Phase 2 schema has one, so there is nothing here to assert
      and adding the column would be Phase 3 work.
- [x] A failure at `COMMIT` (not at `flush()`) returns `409 {"detail": "conflict"}`
      and leaves no row behind — `test_transactions.py`, following the
      throwaway-route pattern in `test_exception_handlers.py`. The route asserts
      its `flush()` succeeded, so the test cannot silently degrade into a
      duplicate of the in-handler path. Verified against the pre-fix code: it
      returns `200 {"status": "flushed"}` with the write discarded.
- [x] The route-class guard test fails if any `/api` route depending on `get_db`
      is not a `TransactionRoute`. It walks nested `_IncludedRouter` mounts and
      the full dependency tree, and carries a meta-test that adds a
      `route_class`-less router and asserts the guard catches it — without which
      the guard would pass vacuously.
- [x] The expired-token test builds the app with `Settings(session_ttl_days=0)`
      instead of rewriting `sessions.expires_at` in the database; the old
      reach-around is deleted. Parametrized over **both** `issue_token` call
      sites (`register` and `login`) — a regression that dropped the injected
      `Settings` in only one would otherwise pass.
- [x] `Settings(session_ttl_days=-1)` raises `ValidationError`; `0` is accepted.
- [x] `change-password`: wrong current password `403`; short new password `422`;
      success `200` with a working new token, the caller's old token and a
      second device's token both `401`.
- [x] `cd backend && uv run pytest` passes.

## Exit criteria

- [x] Existing recipe CRUD still works through authenticated HTTP.
- [x] Registration and login work through the factory-built test app.
- [x] The test seam (`conftest.py` + `create_app` / `make_engine`) was hand-authored
      by a non-author before route work, attaches the `connect` / `begin` listeners,
      and the listener-parity test passes (R-8).
- [x] Scope fence passed (R-10, [`../plan.md` §Phase scope fence](../plan.md#phase-scope-fence-and-handoff-contract)):
      every changed behavior traces to this phase and its linked spec; no
      deferred/context document authorized work.
- [x] Diff review gate passed (R-6, [`../plan.md` §Execution rules](../plan.md#execution-rules)):
      a non-author reviewer checked this phase's diff and new tests against
      `spec.md` §7 and §§1, 3, 5.1, 6.
- [x] **Hardening diff review gate passed (R-6)** — a non-author reviewer
      checked the hardening diff and its new tests against `spec.md` §7 and
      §§1, 3.1, 3.2, 3.3, 3.4, 5.1, 6, walking the commit-time failure path
      rather than trusting a green suite. Separate model pass, PASS with no
      blocking or should-fix findings. The reviewer traced FastAPI 0.141.1's
      `get_request_handler` to confirm serialization completes and the commit
      runs before any bytes reach the wire, and ran four mutation probes — the
      caller's-own-session-survives regression, a removed `TransactionRoute`
      commit, a dropped `route_class=`, and a naive `process_result_value` —
      each of which a test caught.
- [x] Phase complete; update the status table in [`../plan.md`](../plan.md)
      back to `Complete`.
