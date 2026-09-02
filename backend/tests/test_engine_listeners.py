"""R-8 listener-parity test.

Proves the production `connect` and `begin` listeners wired by
`app.database.make_engine` are actually active on the engine the test fixtures
use, so a regression that drops or reorders either listener FAILS a test here
instead of silently disabling the SQLite write lock.

Which regression each assertion catches:

- Missing / broken `connect` listener (in whole, or just its
  `PRAGMA foreign_keys=ON`)
    -> `PRAGMA foreign_keys` returns 0
    -> `test_connect_listener_pragmas` FAILS.  (Verified by hand: neutering the
       listener makes this assertion fail `assert 0 == 1`.)

- Missing `begin` listener
    -> with `isolation_level=None` (set by the `connect` listener) pysqlite no
       longer auto-begins, and nothing issues `BEGIN IMMEDIATE`, so the first
       connection's write auto-commits and holds no lock; the second writer then
       succeeds and no `OperationalError` is raised
    -> `test_begin_immediate_serializes_writers` FAILS `pytest.raises`.
       (Verified by hand: it fails "DID NOT RAISE OperationalError", instantly.)

Known blind spot: dropping *only* `PRAGMA busy_timeout=5000` from the `connect`
listener is NOT caught here, and cannot be by any test -- pysqlite's own default
is `sqlite3.connect(timeout=5.0)`, i.e. an identical 5000 ms C-level busy
timeout, so `PRAGMA busy_timeout` still reads 5000 and the wait below is still
~5 s. The spec (§3.2) still mandates the explicit PRAGMA; it is defensive
redundancy. The elapsed-time assertion below therefore proves only that *a* real
busy-wait happens (the lock is genuinely held), not which layer supplies the
timeout.
"""

import time

import pytest
from sqlalchemy.exc import OperationalError

from app.database import make_engine

# busy_timeout is 5000 ms in make_engine. A genuine lock wait must take roughly
# that long; an instant failure means the timeout PRAGMA never ran.
_MIN_WAIT_SECONDS = 3.0
_MAX_WAIT_SECONDS = 30.0  # generous upper bound; only trips on a real hang


def test_connect_listener_pragmas(test_engine) -> None:
    """The fixture engine (production `make_engine`, in-memory StaticPool) applies
    the `connect` listener PRAGMAs to every DBAPI connection."""
    with test_engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert conn.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000


def test_begin_immediate_serializes_writers(tmp_path) -> None:
    """A file-backed engine so two real connections contend. While one holds a
    write transaction, the second connection's write blocks and then times out
    under `busy_timeout` -- it must raise `OperationalError` ("database is
    locked"), and only after waiting, not instantly."""
    engine = make_engine(f"sqlite:///{tmp_path / 'parity.db'}")
    holder = None
    holder_txn = None
    contender = None
    try:
        with engine.begin() as setup:
            setup.exec_driver_sql("CREATE TABLE t (id INTEGER PRIMARY KEY, v INTEGER)")
            setup.exec_driver_sql("INSERT INTO t (id, v) VALUES (1, 0)")

        # Connection 1 opens a transaction. The `begin` listener turns this into
        # BEGIN IMMEDIATE -> RESERVED write lock. The write keeps the lock held
        # for the duration; if the `begin` listener were gone this statement
        # would auto-commit and hold nothing.
        holder = engine.connect()
        holder_txn = holder.begin()
        holder.exec_driver_sql("UPDATE t SET v = 1 WHERE id = 1")

        # Connection 2 tries to write. It must block on the lock and eventually
        # time out under busy_timeout (5 s) rather than fail immediately.
        contender = engine.connect()
        start = time.monotonic()
        with pytest.raises(OperationalError) as excinfo:
            with contender.begin():
                contender.exec_driver_sql("UPDATE t SET v = 2 WHERE id = 1")
        elapsed = time.monotonic() - start

        orig = str(excinfo.value.orig)
        assert "database is locked" in orig or "database is busy" in orig, orig
        assert elapsed >= _MIN_WAIT_SECONDS, (
            f"second writer failed after only {elapsed:.2f}s; the write lock was "
            "not genuinely held (no real busy-wait occurred)"
        )
        assert elapsed < _MAX_WAIT_SECONDS, f"second writer hung for {elapsed:.2f}s"
    finally:
        if holder_txn is not None:
            try:
                holder_txn.rollback()
            except Exception:
                pass
        if holder is not None:
            holder.close()
        if contender is not None:
            contender.close()
        engine.dispose()
