"""Authentication schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class RegisterRequest(BaseModel):
    """Request body for user registration."""

    username: str = Field(
        pattern=r"^[A-Za-z0-9_.-]{3,50}$",
        description="Username: 3-50 chars, alphanumeric + underscore, dot, dash",
    )
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Password: 8-128 characters",
    )
    code: str | None = Field(
        default=None,
        description="Registration code if required by settings",
    )


class LoginRequest(BaseModel):
    """Request body for user login."""

    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    """Request body for rotating the current user's password."""

    current_password: str = Field(
        description="The caller's current password; must match the stored hash",
    )
    new_password: str = Field(
        min_length=8,
        max_length=128,
        description="New password: 8-128 characters (the same rule register applies)",
    )


class UserMini(ORMModel):
    """Minimal user representation."""

    id: int
    username: str


class UserRead(ORMModel):
    """User data for authenticated responses."""

    id: int
    username: str
    created_at: datetime


class TokenResponse(BaseModel):
    """Response containing a new authentication token."""

    token: str
    user: UserRead
