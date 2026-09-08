"""Test seam for the backend suite (R-8, Phase 2).

No `app.dependency_overrides` anywhere. The app under test is built with the
production factory `create_app(settings, engine)` over an engine produced by
the production `make_engine(...)`. Because `make_engine` recognises the
in-memory URL and returns a `StaticPool` engine, the fixture engine carries the
`connect` / `begin` listeners as production (`isolation_level=None`,
`PRAGMA foreign_keys=ON`, `PRAGMA busy_timeout=5000`, `BEGIN IMMEDIATE`). See
`test_engine_listeners.py` for the listener-parity assertions (R-8).

Isolation: each test gets a fresh `make_engine("sqlite://")` engine. A
StaticPool in-memory database lives only as long as its single pooled
connection, so a new engine per test == a brand-new empty schema.
`create_app`'s lifespan runs `Base.metadata.create_all` when `TestClient` is
entered as a context manager.
"""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.engine import Engine

from app.config import Settings
from app.database import make_engine
from app.main import create_app

# Fixed registration code so the auth fixtures below (and Pass 2c's auth tests)
# have a stable secret. `allow_registration=True` opens the endpoint.
REGISTRATION_CODE = "phase2-test-registration-code"

_TEST_USERNAME = "tester"
_TEST_PASSWORD = "correct horse battery"  # Valid length for RegisterRequest.


@pytest.fixture(name="test_settings")
def test_settings_fixture() -> Settings:
    """A `Settings` instance wired for the in-memory test app.

    Explicit kwargs outrank env vars and `.env` in pydantic-settings, so this is
    hermetic regardless of the developer's environment.
    """
    return Settings(
        database_url="sqlite://",
        allow_registration=True,
        registration_code=REGISTRATION_CODE,
    )


@pytest.fixture(name="test_engine")
def test_engine_fixture(test_settings: Settings) -> Iterator[Engine]:
    """Create an in-memory engine with the production listeners attached."""
    engine = make_engine(test_settings.database_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(name="built_app")
def built_app_fixture(test_settings: Settings, test_engine: Engine) -> FastAPI:
    """Build the test app with the production factory and no overrides."""
    return create_app(test_settings, test_engine)


@pytest.fixture(name="client")
def client_fixture(built_app: FastAPI) -> Iterator[TestClient]:
    """Yield a client whose lifespan creates the in-memory database schema."""
    with TestClient(built_app) as c:
        yield c


# --------------------------------------------------------------------------- #
# Auth fixtures.
#
# These call `POST /api/auth/register` and `POST /api/auth/login`, which Pass 2c
# implements. They are written against those endpoints now (per R-8), but no
# test consumes them yet, so they are not exercised until 2c lands auth. They
# are NOT fake-auth stubs: they hit the real endpoints and will fail loudly
# (404) if used before 2c. Pass 2c migrates the recipe tests onto `auth_client`.
# --------------------------------------------------------------------------- #


def _response_error(action: str, response: Response) -> str:
    return f"{action} failed: {response.status_code} {response.text}"


def _register_and_login(c: TestClient, username: str, password: str) -> dict:
    registration = {
        "username": username,
        "password": password,
        "code": REGISTRATION_CODE,
    }
    reg = c.post(
        "/api/auth/register",
        json=registration,
    )
    assert reg.status_code == 201, _response_error("register", reg)
    login = c.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200, _response_error("login", login)
    body = login.json()
    assert "token" in body, body
    return body


@pytest.fixture(name="user")
def user_fixture(client: TestClient) -> dict:
    """The registered user's `UserRead` (id, username, created_at)."""
    return _register_and_login(client, _TEST_USERNAME, _TEST_PASSWORD)["user"]


@pytest.fixture(name="auth_client")
def auth_client_fixture(client: TestClient) -> TestClient:
    """`client` with a valid `Authorization: Bearer <token>` header attached."""
    body = _register_and_login(client, _TEST_USERNAME, _TEST_PASSWORD)
    token = body["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
