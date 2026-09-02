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


def test_auth_expired_token(client: TestClient, test_engine, test_settings) -> None:
    """Authorization with expired token returns 401."""
    # Create a user and register them.
    app = create_app(test_settings, test_engine)
    with TestClient(app) as c:
        # Register a user to get a token.
        reg = c.post(
            "/api/auth/register",
            json={"username": "expiretest", "password": "password123", "code": REGISTRATION_CODE},
        )
        token_response = reg.json()
        token = token_response["token"]

        # Directly manipulate the database to expire the token.
        from sqlalchemy import func

        # Get a fresh session to the same engine.
        from app.database import make_session_factory

        factory = make_session_factory(test_engine)
        db = factory()
        try:
            session_row = db.scalar(select(SessionModel).where(SessionModel.token == token))
            assert session_row is not None
            # Set expires_at to the past.
            session_row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
            db.commit()
        finally:
            db.close()

        # Now try to use the expired token.
        c.headers["Authorization"] = f"Bearer {token}"
        resp = c.get("/api/auth/me")
        assert resp.status_code == 401
        assert resp.json() == {"detail": "not authenticated"}


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


