"""Authentication router."""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, func
from sqlalchemy.sql import select

from app.config import Settings
from app.database import SessionDep, TransactionRoute
from app.models import Session as SessionModel
from app.models import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserRead,
)
from app.security import CurrentUser, hash_password, issue_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"], route_class=TransactionRoute)


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
    session_row = issue_token(db, user, settings)

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
    session_row = issue_token(db, user, settings)

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


@router.post("/change-password", status_code=status.HTTP_200_OK, response_model=TokenResponse)
def change_password(
    payload: ChangePasswordRequest,
    user: CurrentUser,
    db: SessionDep,
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """Rotate the current user's password (spec.md §5.1).

    Flow (order matters):
    1. Pydantic validation -> 422 (where a too-short new_password fails)
    2. Wrong current_password -> 403 {"detail": "incorrect password"}.
       Not 401: the presented token is valid and the *action* is refused.
    3. Replace the stored hash.
    4. Delete EVERY session for the user, including the caller's own.
    5. Issue a fresh token -> 200 TokenResponse.

    The device that changed the password stays signed in on the new token; every
    other device is signed out immediately.
    """
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="incorrect password",
        )

    user.password_hash = hash_password(payload.new_password)

    # Unconditional: no `AND id != current` special case. The caller's own token
    # dies here too and is replaced by the one issued below.
    db.execute(delete(SessionModel).where(SessionModel.user_id == user.id))
    db.flush()

    session_row = issue_token(db, user, settings)

    return TokenResponse(
        token=session_row.token,
        user=UserRead.model_validate(user),
    )


@router.get("/me", response_model=UserRead)
def get_current(user: CurrentUser) -> UserRead:
    """Get the current authenticated user's profile."""
    return UserRead.model_validate(user)
