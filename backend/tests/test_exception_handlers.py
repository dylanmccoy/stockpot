"""Global exception-handler behavior (spec.md §3.3, §6, §0 status-code table).

`_to_409_if_locked_else_500` must translate an `OperationalError` whose message
names a SQLite write-lock ("database is locked" / "database is busy") to HTTP
409, and let *every other* `OperationalError` surface as HTTP 500 — never 409.

`test_engine_listeners.py` (R-8) covers the lock path at the engine layer. This
file covers the handler's *predicate* through real HTTP on a factory-built app:
the lock message -> 409, a non-lock message -> 500. A regression that loosens
the predicate (always-409, or always re-raise) fails exactly one of the two
assertions below.

Test-only: a throwaway route on a local `create_app(...)` instance raises a
synthetic `OperationalError`. No production code, no `dependency_overrides`, the
`_to_409_if_locked_else_500` predicate is untouched.
"""

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.database import make_engine
from app.main import create_app


def _operational_error(message: str) -> OperationalError:
    """A SQLAlchemy OperationalError whose `str(exc.orig)` is `message`."""
    return OperationalError("SELECT 1", {}, Exception(message))


def _app_raising(message: str):
    settings = Settings(
        database_url="sqlite://",
        allow_registration=True,
        registration_code="x",
    )
    engine = make_engine(settings.database_url)
    app = create_app(settings, engine)

    boom = APIRouter()

    @boom.get("/api/_boom")
    def _boom() -> None:  # pragma: no cover - body is the point
        raise _operational_error(message)

    app.include_router(boom)
    return app, engine


def test_non_lock_operationalerror_surfaces_as_500() -> None:
    """A non-lock OperationalError is NOT translated to 409 — it is a 500."""
    app, engine = _app_raising("no such column: nope")
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/_boom")
        assert resp.status_code == 500
        # The 409 path returns a JSON `{"detail": "conflict"}` body; the 500 path
        # is Starlette's plain "Internal Server Error". Guard against a handler
        # that returns the 409 body under a 500 status, or vice versa.
        assert "conflict" not in resp.text
    finally:
        engine.dispose()


def test_lock_operationalerror_is_translated_to_409() -> None:
    """The same handler still maps a write-lock OperationalError to 409.

    Paired with the test above so that loosening the predicate to "always 500 /
    always re-raise" fails here, and loosening it to "always 409" fails there.
    """
    app, engine = _app_raising("database is locked")
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/_boom")
        assert resp.status_code == 409
        assert resp.json() == {"detail": "conflict"}
    finally:
        engine.dispose()
