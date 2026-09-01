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
- [ ] Rebuild test fixtures around the app factory with no dependency override.
- [ ] Add `test_auth.py` and migrate existing recipe tests to `auth_client`.

## Verification

- [ ] Registration defaults off and requires the configured code when enabled.
- [ ] `last_used_at` persists as part of the request transaction.
- [ ] Missing, malformed, wrong-scheme, unknown, and expired tokens return 401.
- [ ] `cd backend && uv run pytest` passes.

## Exit criteria

- [ ] Existing recipe CRUD still works through authenticated HTTP.
- [ ] Registration and login work through the factory-built test app.
- [ ] Phase complete; update the status table in [`../plan.md`](../plan.md).
