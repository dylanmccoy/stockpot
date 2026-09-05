"""Recover one forgotten household password against a stopped deployment's
database (private-household-deployment ticket 03b).

`recover_password` replaces a single existing user's stored password hash with
a fresh argon2 hash — `app.security.hash_password`, the same facility
`POST /api/auth/change-password` uses — and deletes every session row for that
user, so the member's old password and every old session token stop working at
once. It writes straight to the configured database while the app is stopped;
it is an operational action for the owner, not a new unauthenticated reset
endpoint.

Only the one named account is touched: other users, their sessions, and every
household record are left exactly as they were. An unknown username, or a
password that fails the register rule, is refused without mutating anything.
Passwords and tokens are never returned, logged, or echoed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import delete, func, inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.sql import select

from app.database import make_engine
from app.models import Session as SessionModel
from app.models import User  # importing the module also populates Base.metadata
from app.schemas.auth import RegisterRequest
from app.security import hash_password


class RecoverError(Exception):
    """Password recovery failed; nothing in the database was changed."""


@dataclass
class RecoverResult:
    """Outcome of a `recover_password` run. Carries the stored username only —
    never the new password or its hash."""

    username: str
    sessions_revoked: int


def recover_password(
    database_url: str, username: str, new_password: str
) -> RecoverResult:
    """Set the password of the existing account `username` in the database at
    `database_url` to `new_password` and revoke all of its sessions. Returns
    the stored username and how many session rows were deleted.

    Raises `RecoverError` — changing nothing — if the target database is
    missing or has no schema, if `username`/`new_password` fail
    `RegisterRequest`'s rules, if no such account exists, or if the write
    itself fails.
    """
    # The register endpoint's username + password rules without the HTTP layer.
    # A real stored username always satisfies the charset rule, so in practice
    # this guards the 8-128 password length; kept inline as a deliberate mirror
    # of routers/auth.py (backend/CLAUDE.md: a boundary change, not a refactor).
    try:
        RegisterRequest(username=username, password=new_password)
    except ValidationError as exc:
        raise RecoverError(
            f"invalid recovery input: {'; '.join(e['msg'] for e in exc.errors())}"
        ) from exc

    # Fail before touching SQLite for a `sqlite:///` path that isn't there —
    # otherwise the connect below creates a stray 0-byte file on a typo'd URL.
    if database_url.startswith("sqlite:///"):
        raw = database_url.removeprefix("sqlite:///")
        if raw and raw != ":memory:" and not Path(raw).exists():
            raise RecoverError(
                f"target database not found: {raw} — point at the deployment's "
                "database file"
            )

    engine = make_engine(database_url)
    try:
        if "users" not in inspect(engine).get_table_names():
            raise RecoverError(
                f"target database has no schema: {database_url} — point at the "
                "deployment's database file"
            )

        try:
            with Session(engine) as db:
                user = db.scalar(
                    select(User).where(func.lower(User.username) == username.lower())
                )
                if user is None:
                    raise RecoverError(
                        f"no such account: {username!r} — nothing was changed"
                    )

                user.password_hash = hash_password(new_password)
                revoked = db.execute(
                    delete(SessionModel).where(SessionModel.user_id == user.id)
                ).rowcount
                stored_username = user.username
                db.commit()
        except SQLAlchemyError as exc:
            raise RecoverError(
                f"writing to {database_url} failed, nothing was changed: {exc}"
            ) from exc

        return RecoverResult(username=stored_username, sessions_revoked=revoked)
    finally:
        engine.dispose()
