"""Authentication router."""

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.sql import select

from app.config import Settings
from app.database import SessionDep, get_db
from app.models import Session as SessionModel
from app.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserRead
from app.security import CurrentUser, hash_password, issue_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def get_settings(request: Request) -> Settings:
    """Retrieve settings from app state."""
    return request.app.state.settings


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=TokenResponse)
def register(
    payload: RegisterRequest,
    db: SessionDep,
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """Register a new user.

    Flow (order matters):
    1. Pydantic validation -> 422
    2. Registration disabled -> 403
    3. Invalid registration code -> 403
    4. Username already taken -> 409
    5. Create user and issue token -> 201 TokenResponse
    """
    # Check if registration is allowed.
    if not settings.allow_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="registration disabled",
        )

    # Check registration code if configured.
    if settings.registration_code:
        if not secrets.compare_digest(payload.code or "", settings.registration_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="invalid registration code",
            )

    # Check for existing user (case-insensitive).
    existing = db.scalar(
        select(User).where(func.lower(User.username) == payload.username.lower())
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="username taken",
        )

    # Create the user.
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.flush()

    # Issue a token.
    session_row = issue_token(db, user)

    return TokenResponse(
        token=session_row.token,
        user=UserRead.model_validate(user),
    )


@router.post("/login", status_code=status.HTTP_200_OK, response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: SessionDep,
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """Authenticate a user.

    Returns a token if credentials are valid.
    Returns 401 for any authentication failure (same message for both cases).
    """
    # Lookup user by lower(username).
    user = db.scalar(
        select(User).where(func.lower(User.username) == payload.username.lower())
    )

    # If user not found, verify against dummy hash for timing safety.
    if user is None:
        from app.security import _DUMMY_HASH

        verify_password(payload.password, _DUMMY_HASH)  # noqa: F841 (unused, for timing)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid username or password",
        )

    # Verify password.
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid username or password",
        )

    # Issue token.
    session_row = issue_token(db, user)

    return TokenResponse(
        token=session_row.token,
        user=UserRead.model_validate(user),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    user: CurrentUser,
    db: SessionDep,
) -> None:
    """Logout by deleting the session token.

    The token is validated by CurrentUser dependency; session_row is stashed
    on request.state by get_current_user.
    """
    # The session_row is stashed by get_current_user on the request.
    session_row = getattr(request.state, "session_row", None)
    if session_row is not None:
        db.delete(session_row)


@router.get("/me", response_model=UserRead)
def get_current(user: CurrentUser) -> UserRead:
    """Get the current authenticated user's profile."""
    return UserRead.model_validate(user)
