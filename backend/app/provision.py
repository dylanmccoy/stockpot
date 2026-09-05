"""Provision household login accounts against a stopped deployment's database
(private-household-deployment ticket 03a).

`provision_accounts` creates one user row per intended household member using
the same rules `POST /api/auth/register` applies — `RegisterRequest`'s username
and password validation, the case-insensitive duplicate check, and
`app.security.hash_password` — but without the HTTP layer, without issuing a
session token, and without ever opening the registration window: it writes
straight to the configured database while the app is stopped, so registration
stays closed throughout. Members sign in themselves afterward.

An account whose username already exists (case-insensitively) is left untouched
and reported as skipped, so the procedure is safe to re-run when a member is
added later. Passwords are never returned, logged, or echoed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import ValidationError
from sqlalchemy import func, inspect
from sqlalchemy.orm import Session
from sqlalchemy.sql import select

from app import models  # noqa: F401  — populates Base.metadata with every table
from app.database import make_engine
from app.models import User
from app.schemas.auth import RegisterRequest
from app.security import hash_password


class ProvisionError(Exception):
    """Provisioning failed; no accounts were created."""


@dataclass
class ProvisionResult:
    """Outcome of a `provision_accounts` run. Carries usernames only — never
    passwords or hashes."""

    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def provision_accounts(
    database_url: str, accounts: list[tuple[str, str]]
) -> ProvisionResult:
    """Create a login for each `(username, password)` in `accounts` in the
    database at `database_url`. Returns which usernames were created and which
    already existed.

    Raises `ProvisionError` — committing nothing — if the target database has
    no schema, if any username or password fails `RegisterRequest`'s rules, or
    if two entries collide on username (case-insensitively).
    """
    for username, password in accounts:
        try:
            RegisterRequest(username=username, password=password)
        except ValidationError as exc:
            raise ProvisionError(
                f"invalid account {username!r}: "
                f"{'; '.join(e['msg'] for e in exc.errors())}"
            ) from exc

    lowered = [u.lower() for u, _ in accounts]
    dupes = sorted({u for u in lowered if lowered.count(u) > 1})
    if dupes:
        raise ProvisionError(
            f"the accounts list repeats a username (case-insensitively): "
            f"{', '.join(dupes)}"
        )

    engine = make_engine(database_url)
    try:
        if "users" not in inspect(engine).get_table_names():
            raise ProvisionError(
                f"target database has no schema: {database_url} — start the "
                "deployment once so it creates its tables, then point at that "
                "database file"
            )

        result = ProvisionResult()
        with Session(engine) as db:
            for username, password in accounts:
                existing = db.scalar(
                    select(User).where(
                        func.lower(User.username) == username.lower()
                    )
                )
                if existing is not None:
                    result.skipped.append(existing.username)
                    continue
                db.add(
                    User(username=username, password_hash=hash_password(password))
                )
                result.created.append(username)
            db.commit()
        return result
    finally:
        engine.dispose()
