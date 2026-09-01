# Phase 2 — Authentication and App Factory

## Goal

Introduce app-local database wiring, the request transaction policy, opaque
sessions, registration/login, and authentication gating.

## Specification

- [`spec.md` §1 — users and sessions](../spec.md#1-data-model--backendappmodelspy)
- [`spec.md` §3 — app infrastructure](../spec.md#3-app-infrastructure)
- [`spec.md` §5.1 — auth API](../spec.md#51-auth--routersauthpy-prefix-apiauth)
- [`spec.md` §6 — concurrency and transactions](../spec.md#6-concurrency--transactions)
- Auth and concurrency rows in [`spec.md` §7](../spec.md#7-acceptance-criteria--test-matrix)

## Work

- [ ] Add settings for session lifetime and controlled registration.
- [ ] Implement `make_engine`, `make_session_factory`, request-aware `get_db`,
      and `SessionDep`; retain one default engine and no global `SessionLocal`.
- [ ] Enable foreign keys, busy timeout, and `BEGIN IMMEDIATE` listeners.
- [ ] Implement `create_app(settings, engine)`, app state, health route, and the
      global 409 exception translations.
- [ ] Add `User` and `Session`, including case-insensitive username uniqueness.
- [ ] Add password hashing, token creation, `get_current_user`, and five explicit
      authentication failure paths.
- [ ] Replace the flat `schemas.py` module with a `schemas/` package containing
      `common.py`, `auth.py`, and an `__init__.py` that re-exports their public
      schemas; later phases add `recipe.py`, `inventory.py`, and `grocery.py`.
- [ ] Add auth schemas and register/login/logout/me routes.
- [ ] Gate recipe routes.
- [ ] **Before any route work (R-8),** a reviewer who does not write this phase's
      production code replaces `backend/tests/conftest.py`: delete the
      `dependency_overrides` seam; build the app via
      `create_app(test_settings, test_engine)` with a `make_engine`-built in-memory
      `StaticPool` engine that carries the same `connect` / `begin` listeners as
      production; add `client` / `user` / `auth_client` fixtures. Get one real test
      green through it before the implementation pass extends it per phase.
- [ ] Add `test_auth.py` and migrate existing recipe tests to `auth_client`.

## Verification

- [ ] Registration defaults off and requires the configured code when enabled.
- [ ] `last_used_at` persists as part of the request transaction.
- [ ] Missing, malformed, wrong-scheme, unknown, and expired tokens return 401.
- [ ] A listener-parity test on the fixture engine passes (R-8): `PRAGMA
      foreign_keys` returns `1`, and while a transaction holds the write lock a
      second connection's write blocks and then times out under `busy_timeout` —
      so a missing `connect` / `begin` listener fails a test instead of silently
      disabling the lock.
- [ ] `cd backend && uv run pytest` passes.

## Exit criteria

- [ ] Existing recipe CRUD still works through authenticated HTTP.
- [ ] Registration and login work through the factory-built test app.
- [ ] The test seam (`conftest.py` + `create_app` / `make_engine`) was hand-authored
      by a non-author before route work, attaches the `connect` / `begin` listeners,
      and the listener-parity test passes (R-8).
- [ ] Scope fence passed (R-10, [`../plan.md` §Phase scope fence](../plan.md#phase-scope-fence-and-handoff-contract)):
      every changed behavior traces to this phase and its linked spec; no
      deferred/context document authorized work.
- [ ] Diff review gate passed (R-6, [`../plan.md` §Execution rules](../plan.md#execution-rules)):
      a non-author reviewer checked this phase's diff and new tests against
      `spec.md` §7 and §§1, 3, 5.1, 6.
- [ ] Phase complete; update the status table in [`../plan.md`](../plan.md).
