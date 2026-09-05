"""Provision household login accounts against a stopped deployment's database
(private-household-deployment ticket 03a).

`provision_accounts` creates one user row per intended household member under
the same rules `POST /api/auth/register` applies — `RegisterRequest`'s username
and password validation, `app.security.hash_password`, and a case-insensitive
username check that mirrors the endpoint's — but without the HTTP layer,
without issuing a session token, and without ever opening the registration
window: it writes straight to the configured database while the app is
stopped, so registration stays closed throughout. Members sign in themselves
afterward.

An account whose username already exists (case-insensitively) is left untouched
and reported as skipped, so the procedure is safe to re-run when a member is
added later. Passwords are never returned, logged, or echoed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import func, inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.sql import select

from app.database import make_engine
from app.models import User  # importing the module also populates Base.metadata
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

    Raises `ProvisionError` — committing nothing — if the target database is
    missing or has no schema, if any username or password fails
    `RegisterRequest`'s rules, if two entries collide on username
    (case-insensitively), or if the write itself fails.
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

    # Fail before touching SQLite for a `sqlite:///` path that isn't there —
    # otherwise the connect below creates a stray 0-byte file on a typo'd URL.
    if database_url.startswith("sqlite:///"):
        raw = database_url.removeprefix("sqlite:///")
        if raw and raw != ":memory:" and not Path(raw).exists():
            raise ProvisionError(
                f"target database not found: {raw} — start the deployment once "
                "so it creates its schema, then point at that database file"
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
        try:
            with Session(engine) as db:
                for username, password in accounts:
                    # Mirrors routers/auth.py::register's case-insensitive
                    # username check; kept inline rather than extracted into a
                    # shared service (backend/CLAUDE.md: this is a boundary
                    # change, not a domain-service refactor).
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
        except SQLAlchemyError as exc:
            raise ProvisionError(
                f"writing to {database_url} failed, no accounts created: {exc}"
            ) from exc
        return result
    finally:
        engine.dispose()
