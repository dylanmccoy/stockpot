"""Test seam for the backend suite (R-8, Phase 2).

No `app.dependency_overrides` anywhere. The app under test is built with the
production factory `create_app(settings, engine)` over an engine produced by the
production `make_engine(...)`. Because `make_engine` recognises the in-memory URL
and returns a `StaticPool` engine, the fixture engine carries the *same*
`connect` / `begin` listeners as production (`isolation_level=None`,
`PRAGMA foreign_keys=ON`, `PRAGMA busy_timeout=5000`, `BEGIN IMMEDIATE`). See
`test_engine_listeners.py` for the listener-parity assertions (R-8).

Isolation: each test gets a fresh `make_engine("sqlite://")` engine. A StaticPool
in-memory database lives only as long as its single pooled connection, so a new
engine per test == a brand-new empty schema. `create_app`'s lifespan runs
`Base.metadata.create_all` when `TestClient` is entered as a context manager.
"""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from app.config import Settings
from app.database import make_engine
from app.main import create_app

# Fixed registration code so the auth fixtures below (and Pass 2c's auth tests)
# have a stable secret. `allow_registration=True` opens the endpoint.
REGISTRATION_CODE = "phase2-test-registration-code"

_TEST_USERNAME = "tester"
_TEST_PASSWORD = "correct horse battery"  # 8..128 chars, satisfies RegisterRequest


@pytest.fixture
def test_settings() -> Settings:
    """A `Settings` instance wired for the in-memory test app.

    Explicit kwargs outrank env vars and `.env` in pydantic-settings, so this is
    hermetic regardless of the developer's environment.
    """
    return Settings(
        database_url="sqlite://",
        allow_registration=True,
        registration_code=REGISTRATION_CODE,
    )


@pytest.fixture
def test_engine(test_settings: Settings) -> Iterator[Engine]:
    """The production `make_engine` against an in-memory URL -> StaticPool engine
    with the production `connect` / `begin` listeners attached."""
    engine = make_engine(test_settings.database_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def built_app(test_settings: Settings, test_engine: Engine) -> FastAPI:
    """The app under test, from the production factory. No dependency overrides."""
    return create_app(test_settings, test_engine)


@pytest.fixture
def client(built_app: FastAPI) -> Iterator[TestClient]:
    """Real `TestClient` over the factory-built app. Entering the context manager
    runs the lifespan, which creates the schema on the fresh in-memory engine."""
    with TestClient(built_app) as c:
        yield c


# --------------------------------------------------------------------------- #
# Auth fixtures.
#
# These call `POST /api/auth/register` and `POST /api/auth/login`, which Pass 2c
# implements. They are written against those endpoints now (per R-8) but no test
# consumes them yet, so they are not exercised until 2c lands auth. They are NOT
# fake-auth stubs: they hit the real endpoints and will fail loudly (404) if used
# before 2c. Pass 2c migrates the recipe tests onto `auth_client`.
# --------------------------------------------------------------------------- #


def _register_and_login(c: TestClient, username: str, password: str) -> dict:
    reg = c.post(
        "/api/auth/register",
        json={"username": username, "password": password, "code": REGISTRATION_CODE},
    )
    assert reg.status_code == 201, f"register failed: {reg.status_code} {reg.text}"
    login = c.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200, f"login failed: {login.status_code} {login.text}"
    body = login.json()
    assert "token" in body, body
    return body


@pytest.fixture
def user(client: TestClient) -> dict:
    """The registered user's `UserRead` (id, username, created_at)."""
    return _register_and_login(client, _TEST_USERNAME, _TEST_PASSWORD)["user"]


@pytest.fixture
def auth_client(client: TestClient) -> TestClient:
    """`client` with a valid `Authorization: Bearer <token>` header attached."""
    body = _register_and_login(client, _TEST_USERNAME, _TEST_PASSWORD)
    client.headers["Authorization"] = f"Bearer {body['token']}"
    return client
