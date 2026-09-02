from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Request, Response
from fastapi.routing import APIRoute
from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

from app.config import settings


class Base(DeclarativeBase):
    pass


class UtcDateTime(TypeDecorator):
    """A timezone-aware datetime column that survives SQLite.

    SQLite has no timezone type: a value written through `DateTime(timezone=True)`
    comes back *naive*, which would break the explicit-UTC-offset guarantee on
    every read path — including raw-SQL paths that bypass the ORM. This decorator
    normalizes on write and re-attaches UTC on read, in one place (spec.md §3.2).
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            # A naive value is taken to already be UTC.
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


def make_engine(url: str) -> Engine:
    """Create a SQLAlchemy engine with SQLite-specific configuration."""
    connect_args = {"check_same_thread": False}
    pool_kwargs = {}

    # In-memory SQLite needs StaticPool.
    if url in ("sqlite://", "sqlite:///:memory:"):
        pool_kwargs["poolclass"] = StaticPool

    engine = create_engine(url, connect_args=connect_args, **pool_kwargs)

    # Set isolation_level to None and enable foreign keys + busy timeout on connect.
    @event.listens_for(engine, "connect")
    def on_connect(dbapi_conn, connection_record):
        dbapi_conn.isolation_level = None
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    # Begin with IMMEDIATE lock to ensure all requests serialize on writes.
    @event.listens_for(engine, "begin")
    def on_begin(conn):
        conn.exec_driver_sql("BEGIN IMMEDIATE")

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a session factory for the given engine."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


# Module-level default engine (for `uvicorn app.main:app`).
engine = make_engine(settings.database_url)


def get_db(request: Request) -> Iterator[Session]:
    """Dependency: own the session's lifetime — but NOT the commit.

    The commit belongs to `TransactionRoute` below. Post-`yield` dependency code
    runs *after* the response has been generated, so an exception raised by a
    commit here can no longer be converted to a 409 — the caller would receive a
    200 with the write silently discarded (spec.md §3.2, §6).
    """
    factory = request.app.state.session_factory
    db = factory()
    request.state.db = db  # TransactionRoute reads it from here.
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


SessionDep = Annotated[Session, Depends(get_db)]


class TransactionRoute(APIRoute):
    """Route class that owns the request transaction's commit (spec.md §3.2, §6).

    The commit runs inside `wrap_app_handling_exceptions` and before the response
    is sent, so an `IntegrityError` or a `SQLITE_BUSY` raised by `COMMIT` reaches
    the global handlers in `main.py` and returns 409 — exactly like an in-handler
    failure. Response serialization completes before the commit, so no ORM
    attribute is touched post-commit and `expire_on_commit` needs no change.

    A route with no database dependency leaves `request.state.db` unset and the
    wrapper no-ops, so `/api/health` needs no special case.
    """

    def get_route_handler(self):
        original = super().get_route_handler()

        async def custom(request: Request) -> Response:
            response = await original(request)
            db = getattr(request.state, "db", None)
            if db is not None:
                db.commit()
            return response

        return custom
