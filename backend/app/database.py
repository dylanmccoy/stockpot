from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings


class Base(DeclarativeBase):
    pass


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
    """Dependency: yield a session, commit on success, rollback on exception."""
    factory = request.app.state.session_factory
    db = factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


SessionDep = Annotated[Session, Depends(get_db)]
