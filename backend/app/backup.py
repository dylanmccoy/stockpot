"""Live SQLite snapshot via the online backup API (private-household-deployment
ticket 02a).

`sqlite3.Connection.backup()` copies a consistent snapshot page-by-page while
the source database is open and being written — unlike a raw file copy, which
can capture a torn write mid-transaction. A snapshot is written to a hidden
temp file in the destination directory and only renamed to its final,
timestamped name after the copy succeeds, so a missing source, an unwritable
destination, or a copy interrupted partway never leaves behind a partial file
under the public name, and never touches any earlier snapshot already there.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class BackupError(Exception):
    """A backup attempt failed; no new snapshot was published."""


def create_backup(source: Path | str, dest_dir: Path | str, *, now: datetime | None = None) -> Path:
    """Snapshot the SQLite database at `source` into a new timestamped file in
    `dest_dir`. Returns the snapshot's path on success.

    Raises `BackupError` — leaving `dest_dir` exactly as it was — if `source`
    doesn't exist, `dest_dir` can't be created/written, or the online backup
    itself fails partway.
    """
    source = Path(source)
    dest_dir = Path(dest_dir)

    if not source.is_file():
        raise BackupError(f"source database not found: {source}")

    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BackupError(f"cannot create destination directory {dest_dir}: {exc}") from exc

    # Operator-only access, enforced on every run (not just when the directory
    # is freshly created) so a destination that drifted to laxer permissions
    # gets tightened back up rather than silently staying open. Best effort:
    # ownership by another user (e.g. a shared/root-managed path) can make this
    # a no-op, which is a host-configuration concern outside this function.
    try:
        os.chmod(dest_dir, 0o700)
    except OSError:
        pass

    timestamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    final_path = dest_dir / f"recipe-{timestamp}.db"
    tmp_path = dest_dir / f".{final_path.name}.tmp"
    tmp_path.unlink(missing_ok=True)

    try:
        _run_online_backup(source, tmp_path)
        os.chmod(tmp_path, 0o600)
        tmp_path.replace(final_path)
    except (OSError, sqlite3.Error) as exc:
        tmp_path.unlink(missing_ok=True)
        raise BackupError(f"backup of {source} failed: {exc}") from exc

    return final_path


def _run_online_backup(source: Path, tmp_path: Path) -> None:
    """Copy `source` into a fresh file at `tmp_path` via SQLite's backup API."""
    src_conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=30)
    try:
        dst_conn = sqlite3.connect(tmp_path, timeout=30)
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()
