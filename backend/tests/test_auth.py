"""Authentication tests."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as SQLAlchemySession

from app.config import Settings
from app.database import make_engine
from app.main import create_app
from app.models import Session as SessionModel
from app.models import User
from tests.conftest import REGISTRATION_CODE


# ============================================================================
# Registration tests
# ============================================================================


def test_register_disabled_by_default(client: TestClient) -> None:
    """When allow_registration=False, register endpoint rejects with 403."""
    # Create a client with default (disabled) registration.
    settings = Settings(database_url="sqlite://")
    engine = make_engine(settings.database_url)
    app = create_app(settings, engine)
    with TestClient(app) as c:
        resp = c.post(
            "/api/auth/register",
            json={"username": "user1", "password": "password123"},
        )
        assert resp.status_code == 403
        assert resp.json() == {"detail": "registration disabled"}
    engine.dispose()


def test_register_requires_code_when_set(client: TestClient) -> None:
    """When registration_code is set, missing or wrong code returns 403."""
    # Prepare a request without the code.
    resp = client.post(
        "/api/auth/register",
        json={"username": "user1", "password": "password123"},
    )
    assert resp.status_code == 403
    assert resp.json() == {"detail": "invalid registration code"}

    # Wrong code.
    resp = client.post(
        "/api/auth/register",
        json={
            "username": "user1",
            "password": "password123",
            "code": "wrong-code",
        },
    )
    assert resp.status_code == 403
    assert resp.json() == {"detail": "invalid registration code"}


def test_register_duplicate_username_case_insensitive(client: TestClient) -> None:
    """Usernames are unique case-insensitively."""
    # Register the first user.
    resp1 = client.post(
        "/api/auth/register",
        json={"username": "TestUser", "password": "password123", "code": REGISTRATION_CODE},
    )
    assert resp1.status_code == 201

    # Try to register with same username, different case.
    resp2 = client.post(
        "/api/auth/register",
        json={"username": "testuser", "password": "password456", "code": REGISTRATION_CODE},
    )
    assert resp2.status_code == 409
    assert resp2.json() == {"detail": "username taken"}


def test_register_success(client: TestClient) -> None:
    """Successful registration returns 201 with TokenResponse."""
    resp = client.post(
        "/api/auth/register",
        json={
            "username": "newuser",
            "password": "correctpassword",
            "code": REGISTRATION_CODE,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "token" in body
    assert "user" in body
    user = body["user"]
    assert user["username"] == "newuser"
    assert user["id"] > 0
    assert "created_at" in user


def test_register_validation_short_username(client: TestClient) -> None:
    """Username must be 3+ characters."""
    resp = client.post(
        "/api/auth/register",
        json={"username": "ab", "password": "password123", "code": REGISTRATION_CODE},
    )
    assert resp.status_code == 422


def test_register_validation_invalid_username_chars(client: TestClient) -> None:
    """Username must match ^[A-Za-z0-9_.-]{3,50}$."""
    resp = client.post(
        "/api/auth/register",
        json={"username": "user@123", "password": "password123", "code": REGISTRATION_CODE},
    )
    assert resp.status_code == 422


def test_register_validation_short_password(client: TestClient) -> None:
    """Password must be 8+ characters."""
    resp = client.post(
        "/api/auth/register",
        json={"username": "newuser", "password": "short", "code": REGISTRATION_CODE},
    )
    assert resp.status_code == 422


def test_register_validation_long_password(client: TestClient) -> None:
    """Password must be <= 128 characters."""
    resp = client.post(
        "/api/auth/register",
        json={
            "username": "newuser",
            "password": "a" * 129,
            "code": REGISTRATION_CODE,
        },
    )
    assert resp.status_code == 422


# ============================================================================
# Login tests
# ============================================================================


def test_login_success(client: TestClient) -> None:
    """Successful login returns 200 with TokenResponse."""
    # Register a user first.
    client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
            "password": "correctpassword",
            "code": REGISTRATION_CODE,
        },
    )

    # Login with correct credentials.
    resp = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "correctpassword"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert "user" in body
    user = body["user"]
    assert user["username"] == "testuser"


def test_login_case_insensitive_username(client: TestClient) -> None:
    """Username lookup is case-insensitive."""
    client.post(
        "/api/auth/register",
        json={
            "username": "TestUser",
            "password": "correctpassword",
            "code": REGISTRATION_CODE,
        },
    )

    # Login with different case.
    resp = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "correctpassword"},
    )
    assert resp.status_code == 200


def test_login_wrong_password(client: TestClient) -> None:
    """Wrong password returns 401 with generic message."""
    client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
            "password": "correctpassword",
            "code": REGISTRATION_CODE,
        },
    )

    resp = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "wrongpassword"},
    )
    assert resp.status_code == 401
    assert resp.json() == {"detail": "invalid username or password"}


def test_login_unknown_user(client: TestClient) -> None:
    """Unknown user returns 401 with generic message."""
    resp = client.post(
        "/api/auth/login",
        json={"username": "unknownuser", "password": "password123"},
    )
    assert resp.status_code == 401
    assert resp.json() == {"detail": "invalid username or password"}


# ============================================================================
# Logout tests
# ============================================================================


def test_logout_deletes_token(auth_client: TestClient) -> None:
    """Logout deletes the session token, subsequent requests fail."""
    # Get the original token from the auth_client header.
    auth_header = auth_client.headers.get("Authorization")
    assert auth_header is not None

    # Logout should succeed.
    resp = auth_client.post("/api/auth/logout")
    assert resp.status_code == 204

    # After logout, the same token should be rejected.
    resp = auth_client.get("/api/auth/me")
    assert resp.status_code == 401


def test_logout_token_rejected_after_delete(auth_client: TestClient) -> None:
    """After logout, the token is deleted and subsequent requests are rejected."""
    resp1 = auth_client.post("/api/auth/logout")
    assert resp1.status_code == 204

    # Second request with the same (now-deleted) token is rejected.
    resp2 = auth_client.post("/api/auth/logout")
    assert resp2.status_code == 401


# ============================================================================
# GET /api/auth/me tests
# ============================================================================


def test_get_me_success(auth_client: TestClient) -> None:
    """GET /api/auth/me returns the current user."""
    resp = auth_client.get("/api/auth/me")
    assert resp.status_code == 200
    user = resp.json()
    assert "id" in user
    assert "username" in user
    assert "created_at" in user


def test_get_me_unauthenticated(client: TestClient) -> None:
    """GET /api/auth/me without auth returns 401."""
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


# ============================================================================
# Authentication failure paths (5 × 401 from get_current_user)
# ============================================================================


def test_auth_missing_header(client: TestClient) -> None:
    """Missing Authorization header returns 401."""
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "not authenticated"}


def test_auth_malformed_single_part(client: TestClient) -> None:
    """Authorization header with only one part returns 401."""
    client.headers["Authorization"] = "Bearer"
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "not authenticated"}


def test_auth_malformed_three_parts(client: TestClient) -> None:
    """Authorization header with three parts returns 401."""
    client.headers["Authorization"] = "Bearer token extra"
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "not authenticated"}


def test_auth_malformed_empty_scheme(client: TestClient) -> None:
    """Authorization header with empty scheme returns 401."""
    client.headers["Authorization"] = " token"
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "not authenticated"}


def test_auth_malformed_empty_token(client: TestClient) -> None:
    """Authorization header with empty token returns 401."""
    client.headers["Authorization"] = "Bearer "
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "not authenticated"}


def test_auth_wrong_scheme(client: TestClient) -> None:
    """Authorization with non-Bearer scheme returns 401."""
    client.headers["Authorization"] = "Basic dXNlcjpwYXNz"
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "not authenticated"}


def test_auth_unknown_token(client: TestClient) -> None:
    """Authorization with unknown token returns 401."""
    client.headers["Authorization"] = "Bearer unknown_token_here"
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "not authenticated"}


def _issue_token_via(c: TestClient, route: str, username: str, password: str) -> str:
    """Get a token from whichever `issue_token` call site `route` names.

    Both call sites live in `routers/auth.py` and both had to start passing
    `settings` through. Parametrizing over them is what keeps a regression in
    *either* one visible.
    """
    reg = c.post(
        "/api/auth/register",
        json={"username": username, "password": password, "code": REGISTRATION_CODE},
    )
    assert reg.status_code == 201, reg.text
    if route == "register":
        return reg.json()["token"]

    login = c.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert login.status_code == 200, login.text
    return login.json()["token"]


@pytest.mark.parametrize("route", ["register", "login"])
def test_auth_expired_token(test_engine, route: str) -> None:
    """A token issued under `session_ttl_days=0` is already expired -> 401.

    The app is built with `Settings(session_ttl_days=0)` and the token comes out
    of a real auth route (spec.md §7) — both of them, since `issue_token` has two
    call sites and a regression that dropped the injected `Settings` in only one
    would otherwise slip through. Nothing reaches into the database to rewrite
    `expires_at`: that reach-around only existed because `issue_token` used to
    read the module-level settings, and it is deleted.
    """
    expiring_settings = Settings(
        database_url="sqlite://",
        allow_registration=True,
        registration_code=REGISTRATION_CODE,
        session_ttl_days=0,
    )
    app = create_app(expiring_settings, test_engine)
    with TestClient(app) as c:
        token = _issue_token_via(c, route, "expiretest", "password123")

        c.headers["Authorization"] = f"Bearer {token}"
        resp = c.get("/api/auth/me")
        assert resp.status_code == 401
        assert resp.json() == {"detail": "not authenticated"}


@pytest.mark.parametrize("route", ["register", "login"])
def test_session_ttl_days_zero_is_the_only_expiring_knob(
    test_engine, route: str
) -> None:
    """The same flow under the default TTL yields a *working* token.

    Paired with the test above so that an implementation which ignores
    `session_ttl_days` entirely (always-expired or never-expired) fails one of
    the two — at each call site.
    """
    normal_settings = Settings(
        database_url="sqlite://",
        allow_registration=True,
        registration_code=REGISTRATION_CODE,
    )
    app = create_app(normal_settings, test_engine)
    with TestClient(app) as c:
        token = _issue_token_via(c, route, "expiretest", "password123")
        c.headers["Authorization"] = f"Bearer {token}"
        assert c.get("/api/auth/me").status_code == 200


# ============================================================================
# last_used_at persistence test (Phase 2 Verification bullet 2)
# ============================================================================


def test_last_used_at_persists(auth_client: TestClient, test_engine, test_settings) -> None:
    """last_used_at is persisted as part of the request transaction.

    After an authenticated request, a fresh read shows last_used_at advanced
    and committed (visible on a new connection/session).
    """
    # Get the token from auth_client.
    auth_header = auth_client.headers.get("Authorization")
    assert auth_header is not None
    token = auth_header.split(" ")[1]

    # Read the initial last_used_at.
    from app.database import make_session_factory

    factory = make_session_factory(test_engine)
    db1 = factory()
    try:
        session_row = db1.scalar(select(SessionModel).where(SessionModel.token == token))
        assert session_row is not None
        initial_last_used_at = session_row.last_used_at
    finally:
        db1.close()

    # Make an authenticated request (e.g., GET /api/auth/me).
    resp = auth_client.get("/api/auth/me")
    assert resp.status_code == 200

    # Wait a tiny bit to ensure time passes (optional, but helps with flaky tests).
    import time

    time.sleep(0.01)

    # Read last_used_at from a new connection/session.
    db2 = factory()
    try:
        session_row = db2.scalar(select(SessionModel).where(SessionModel.token == token))
        assert session_row is not None
        new_last_used_at = session_row.last_used_at
    finally:
        db2.close()

    # Verify it was advanced and is visible (committed).
    assert new_last_used_at > initial_last_used_at




# ============================================================================
# change-password tests (spec.md §5.1)
# ============================================================================


def _register(c: TestClient, username: str, password: str) -> dict:
    resp = c.post(
        "/api/auth/register",
        json={"username": username, "password": password, "code": REGISTRATION_CODE},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_change_password_wrong_current_password_403(client: TestClient) -> None:
    """A wrong `current_password` is 403, not 401: the token is valid and the
    *action* is refused, so telling the client to re-authenticate would be wrong."""
    body = _register(client, "rotator", "original-password")
    client.headers["Authorization"] = f"Bearer {body['token']}"

    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": "not-the-password", "new_password": "brand-new-password"},
    )
    assert resp.status_code == 403
    assert resp.json() == {"detail": "incorrect password"}

    # The old password still works: nothing was rotated.
    login = client.post(
        "/api/auth/login",
        json={"username": "rotator", "password": "original-password"},
    )
    assert login.status_code == 200


def test_change_password_short_new_password_422(client: TestClient) -> None:
    """`new_password` shorter than 8 fails Pydantic validation, before the
    current-password check — the same 8..128 rule `register` applies."""
    body = _register(client, "rotator", "original-password")
    client.headers["Authorization"] = f"Bearer {body['token']}"

    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": "original-password", "new_password": "short"},
    )
    assert resp.status_code == 422


def test_change_password_unauthenticated_401(client: TestClient) -> None:
    """change-password requires a token."""
    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": "whatever0", "new_password": "brand-new-password"},
    )
    assert resp.status_code == 401


def test_change_password_success_rotates_and_signs_out_every_device(
    client: TestClient,
) -> None:
    """Success returns 200 TokenResponse; the new token works, the caller's old
    token is dead, and a second device's token issued before the change is dead.

    This is the whole point of the endpoint: the device that changed the
    password stays signed in on a fresh token, every other device is signed out.
    """
    first = _register(client, "rotator", "original-password")
    old_token = first["token"]

    # A second device signs in before the change.
    second = client.post(
        "/api/auth/login",
        json={"username": "rotator", "password": "original-password"},
    )
    assert second.status_code == 200
    second_device_token = second.json()["token"]
    assert second_device_token != old_token

    client.headers["Authorization"] = f"Bearer {old_token}"
    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": "original-password", "new_password": "brand-new-password"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"token", "user"}
    new_token = body["token"]
    assert body["user"]["username"] == "rotator"
    assert new_token not in (old_token, second_device_token)

    # The freshly issued token authenticates.
    client.headers["Authorization"] = f"Bearer {new_token}"
    assert client.get("/api/auth/me").status_code == 200

    # The caller's own old token is gone — deletion is unconditional.
    client.headers["Authorization"] = f"Bearer {old_token}"
    assert client.get("/api/auth/me").status_code == 401

    # So is the second device's.
    client.headers["Authorization"] = f"Bearer {second_device_token}"
    assert client.get("/api/auth/me").status_code == 401


def test_change_password_new_password_is_the_one_that_logs_in(
    client: TestClient,
) -> None:
    """The stored hash is actually replaced, and committed."""
    body = _register(client, "rotator", "original-password")
    client.headers["Authorization"] = f"Bearer {body['token']}"
    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": "original-password", "new_password": "brand-new-password"},
    )
    assert resp.status_code == 200, resp.text

    del client.headers["Authorization"]
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "rotator", "password": "original-password"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "rotator", "password": "brand-new-password"},
        ).status_code
        == 200
    )


# ============================================================================
# Datetime serialization (spec.md §1 "Mechanical defaults", §3.2 UtcDateTime)
# ============================================================================


def test_user_created_at_carries_an_explicit_utc_offset(client: TestClient) -> None:
    """`created_at` round-trips through SQLite with its UTC offset intact.

    Without `UtcDateTime`, SQLite hands back a naive value and this serializes
    without an offset — a client would read it as local time.
    """
    body = _register(client, "tzuser", "original-password")
    created_at = body["user"]["created_at"]
    assert created_at.endswith("+00:00") or created_at.endswith("Z"), created_at

    parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)

    client.headers["Authorization"] = f"Bearer {body['token']}"
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["created_at"] == created_at


def test_session_datetimes_are_tz_aware_on_read(
    client: TestClient, test_engine
) -> None:
    """Read straight back through the ORM: every `sessions` datetime is aware."""
    body = _register(client, "tzuser", "original-password")

    from app.database import make_session_factory

    db: SQLAlchemySession = make_session_factory(test_engine)()
    try:
        row = db.scalar(select(SessionModel).where(SessionModel.token == body["token"]))
        assert row is not None
        for column in ("created_at", "last_used_at", "expires_at"):
            value = getattr(row, column)
            assert value.tzinfo is not None, column
            assert value.utcoffset() == timedelta(0), column
        user = db.get(User, row.user_id)
        assert user is not None
        assert user.created_at.tzinfo is not None
    finally:
        db.close()
