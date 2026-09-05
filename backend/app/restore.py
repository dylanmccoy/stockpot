"""Rehearse recovery of a live SQLite snapshot into a separate database
(private-household-deployment ticket 02b).

`recover_snapshot` validates a snapshot produced by `app.backup.create_backup`
and materializes it at a **new** target path — never an existing one, because
replacing a live database in place is ticket 02c. Before the recovered
database is published, every row in `sessions` is deleted: a session token
captured from the snapshot cannot be replayed against the recovered database
(and a session revoked before the snapshot is not revived), so the owner
signs in afresh to inspect the recovered household.

The snapshot and any live database are only ever read, never written.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path
from urllib.request import pathname2url

from app import models  # noqa: F401  — populates Base.metadata with every table
from app.database import Base


class RestoreError(Exception):
    """A recovery attempt failed; no recovered database was published."""


def recover_snapshot(snapshot: Path | str, target: Path | str) -> Path:
    """Validate the SQLite snapshot at `snapshot` and write a session-cleared
    copy of it to `target`. Returns `target` on success.

    Raises `RestoreError` — leaving `target` absent, and the snapshot and any
    live database untouched — if `snapshot` is missing or is not an intact
    database with this application's full schema, if `target` already exists,
    or if the copy or session-invalidation fails partway.
    """
    snapshot = Path(snapshot)
    target = Path(target)

    if not snapshot.is_file():
        raise RestoreError(f"snapshot not found: {snapshot}")

    if target.exists():
        raise RestoreError(
            f"target already exists: {target} — this step only recovers into a "
            "fresh path; replacing a database in place is a separate procedure"
        )

    _validate_snapshot(snapshot)

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RestoreError(
            f"cannot create target directory {target.parent}: {exc}"
        ) from exc

    tmp_path = target.parent / f".{target.name}.tmp"
    tmp_path.unlink(missing_ok=True)

    try:
        shutil.copyfile(snapshot, tmp_path)
        _invalidate_sessions(tmp_path)
        # Operator-only access on the recovered database itself — it holds the
        # household's records and password hashes, so a rehearsal copy is no
        # more world-readable than a snapshot (spec item 9). The target
        # directory's own permissions are left as the operator chose them.
        os.chmod(tmp_path, 0o600)
        tmp_path.replace(target)
    except (OSError, sqlite3.Error) as exc:
        tmp_path.unlink(missing_ok=True)
        raise RestoreError(f"recovery of {snapshot} failed: {exc}") from exc

    return target


def _validate_snapshot(snapshot: Path) -> None:
    """Reject anything that isn't an intact SQLite database with this app's
    full schema — so a truncated or unrelated file can't be recovered into a
    database that looks successful but fails the moment the app touches it."""
    uri = f"file:{pathname2url(str(snapshot))}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=30)
    except sqlite3.Error as exc:
        raise RestoreError(f"cannot open snapshot {snapshot}: {exc}") from exc

    try:
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            table_names = {
                name
                for (name,) in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        except sqlite3.Error as exc:
            raise RestoreError(
                f"snapshot is not a valid SQLite database: {snapshot} ({exc})"
            ) from exc
    finally:
        conn.close()

    if not integrity or integrity[0] != "ok":
        raise RestoreError(f"snapshot failed its SQLite integrity check: {snapshot}")

    missing = set(Base.metadata.tables) - table_names
    if missing:
        raise RestoreError(
            f"snapshot is not a recipe-app database: {snapshot} "
            f"(missing tables: {', '.join(sorted(missing))})"
        )


def _invalidate_sessions(db_path: Path) -> None:
    """Clear every session row so snapshot-era tokens cannot be replayed."""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        conn.execute("DELETE FROM sessions")
        conn.commit()
    finally:
        conn.close()
