"""Authentication and token management."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from pwdlib import PasswordHash
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy.sql import select

from app.config import Settings, settings
from app.database import SessionDep
from app.models import Session as SessionModel
from app.models import User


def _get_settings(request: Request) -> Settings:
    """Get settings from request app state."""
    return request.app.state.settings


# Module-level argon2 hasher.
_hasher = PasswordHash.recommended()


def hash_password(pw: str) -> str:
    """Hash a password using argon2."""
    return _hasher.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    """Verify a password against a hash."""
    return _hasher.verify(pw, hashed)


# Dummy hash for timing-safe login failure.
_DUMMY_HASH = hash_password(secrets.token_hex(16))


def issue_token(db: SQLAlchemySession, user: User) -> SessionModel:
    """Create a new session token for a user.

    Args:
        db: SQLAlchemy session.
        user: The user to create a token for.

    Returns:
        The created Session ORM row.
    """
    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(days=settings.session_ttl_days)

    session = SessionModel(
        token=token,
        user_id=user.id,
        created_at=now,
        last_used_at=now,
        expires_at=expires_at,
    )
    db.add(session)
    db.flush()
    return session


def get_current_user(
    request: Request,
    db: SessionDep,
    settings: Annotated[Settings, Depends(_get_settings)],
    authorization: str | None = Header(default=None),
) -> User:
    """Dependency to extract and validate the current user from the Authorization header.

    Stashes the SessionModel row on request.state for logout to use.

    Returns:
        The authenticated User.

    Raises:
        HTTPException(401): For any of 5 failure modes:
            - missing authorization header
            - malformed authorization header
            - wrong scheme (not Bearer)
            - unknown token
            - expired token
    """
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
        )

    parts = authorization.split(" ")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
        )

    if parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
        )

    token = parts[1]

    # Lookup the session token.
    session_row = db.scalar(select(SessionModel).where(SessionModel.token == token))
    if session_row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
        )

    # Check expiration (handle naive datetimes from SQLite).
    now = datetime.now(timezone.utc)
    expires_at = session_row.expires_at
    # Normalize naive datetime to UTC.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
        )

    # Update last_used_at for this request (rides the request transaction).
    session_row.last_used_at = now
    db.flush()

    # Stash the session row for logout to use.
    request.state.session_row = session_row

    return session_row.user


CurrentUser = Annotated[User, Depends(get_current_user)]
