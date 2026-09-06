"""Recover a live SQLite snapshot — into a separate rehearsal database
(private-household-deployment ticket 02b) or in place over the configured one
with writers stopped (ticket 02c).

`recover_snapshot` validates a snapshot produced by `app.backup.create_backup`
and materializes it at a **new** target path — never an existing one.

`replace_database` recovers a validated snapshot *over* an existing target,
for the owner replacing the household database after a data loss. It first
preserves the current target as its own snapshot and refuses to go further if
that preservation or its validation fails, so the database being replaced is
never lost. The final swap onto the live path is a single atomic rename of an
already-prepared, already-validated copy.

In both, before the recovered database is published every row in `sessions`
is deleted: a session token captured from the snapshot cannot be replayed
(and a session revoked before the snapshot is not revived), so the owner
signs in afresh. The snapshot, any earlier snapshots, and — until the atomic
swap — the target are only ever read, never written.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.request import pathname2url

from app import models  # noqa: F401  — populates Base.metadata with every table
from app.backup import BackupError, create_backup
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

    try:
        _prepare_recovered_copy(snapshot, tmp_path)
        tmp_path.replace(target)
    except (OSError, sqlite3.Error) as exc:
        tmp_path.unlink(missing_ok=True)
        raise RestoreError(f"recovery of {snapshot} failed: {exc}") from exc

    return target


@dataclass(frozen=True)
class ReplaceResult:
    """A successful in-place replacement: the live database now at `target`,
    and `preserved` — the snapshot of what it replaced."""

    target: Path
    preserved: Path


def replace_database(
    snapshot: Path | str,
    target: Path | str,
    *,
    preserve_dir: Path | str,
) -> ReplaceResult:
    """Replace the existing database at `target` with a validated,
    session-cleared copy of `snapshot`, having first preserved the current
    `target` as a snapshot in `preserve_dir`.

    The application's writers must already be stopped — this works on files,
    not a running server. Returns a `ReplaceResult` naming the live path and
    the preserved copy of the database that was replaced.

    Raises `RestoreError`, leaving `target` byte-for-byte as it was, if:

    - `snapshot` is missing, or is not an intact database with this app's full
      schema;
    - `target` does not already exist (recover into a fresh path instead);
    - preserving the current `target` fails, or the preserved copy does not
      itself validate — the database being replaced is never given up on a bad
      recovery point;
    - preparing or validating the recovered copy fails before the final swap.

    Earlier snapshots in `preserve_dir` and the `snapshot` file are only read.
    """
    snapshot = Path(snapshot)
    target = Path(target)
    preserve_dir = Path(preserve_dir)

    if not snapshot.is_file():
        raise RestoreError(f"snapshot not found: {snapshot}")

    if not target.is_file():
        raise RestoreError(
            f"target database not found: {target} — replacing a database in "
            "place needs an existing target; recover into a fresh path instead"
        )

    _validate_snapshot(snapshot)

    try:
        preserved = create_backup(target, preserve_dir)
    except BackupError as exc:
        raise RestoreError(
            f"refusing to replace {target}: preserving the current database "
            f"failed ({exc}) — {target} is unchanged"
        ) from exc

    try:
        _validate_snapshot(preserved)
    except RestoreError as exc:
        preserved.unlink(missing_ok=True)
        raise RestoreError(
            f"refusing to replace {target}: the preserved copy did not "
            f"validate ({exc}) — {target} is unchanged"
        ) from exc

    tmp_path = target.parent / f".{target.name}.replacing"
    try:
        _prepare_recovered_copy(snapshot, tmp_path)
        _validate_snapshot(tmp_path)
    except (OSError, sqlite3.Error, RestoreError) as exc:
        tmp_path.unlink(missing_ok=True)
        raise RestoreError(
            f"preparing the recovered database from {snapshot} failed ({exc}) "
            f"— {target} is unchanged; preserved copy: {preserved}"
        ) from exc

    try:
        tmp_path.replace(target)
    except OSError as exc:
        tmp_path.unlink(missing_ok=True)
        raise RestoreError(
            f"the final swap onto {target} failed ({exc}) — the database is "
            f"unchanged; preserved copy: {preserved}"
        ) from exc

    return ReplaceResult(target=target, preserved=preserved)


def _prepare_recovered_copy(snapshot: Path, tmp_path: Path) -> None:
    """Copy `snapshot` to `tmp_path`, clear its sessions, and lock it to the
    operator — the shared body of recovering into a fresh path and replacing a
    database in place. Leaves `tmp_path` ready for an atomic rename onto the
    real target; the caller owns cleanup on failure."""
    tmp_path.unlink(missing_ok=True)
    shutil.copyfile(snapshot, tmp_path)
    _invalidate_sessions(tmp_path)
    # Operator-only access on the recovered database itself — it holds the
    # household's records and password hashes, so the copy is no more
    # world-readable than a snapshot (spec item 9). Any target directory's own
    # permissions are left as the operator chose them.
    os.chmod(tmp_path, 0o600)


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
