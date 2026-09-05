"""The operator-facing restore CLI (`scripts/restore.py`), run as a subprocess
exactly as root README.md "Restore rehearsal" documents it."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRIPT = BACKEND_DIR / "scripts" / "restore.py"


def _recipe_shaped_sqlite(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE users (id INTEGER PRIMARY KEY);"
        "CREATE TABLE sessions (id INTEGER PRIMARY KEY, token TEXT);"
        "CREATE TABLE recipes (id INTEGER PRIMARY KEY);"
    )
    conn.execute("INSERT INTO sessions (token) VALUES ('stale-token')")
    conn.commit()
    conn.close()


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=BACKEND_DIR,
        env={**os.environ},
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_cli_success_prints_recovered_path_and_clears_sessions(tmp_path: Path) -> None:
    snapshot = tmp_path / "snap.db"
    _recipe_shaped_sqlite(snapshot)
    target = tmp_path / "rehearsal.db"

    result = _run(["--snapshot", str(snapshot), "--target", str(target)])

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"restore ok: {target}"
    assert target.is_file()

    conn = sqlite3.connect(target)
    try:
        assert conn.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
    finally:
        conn.close()


def test_cli_missing_snapshot_fails_without_creating_target(tmp_path: Path) -> None:
    target = tmp_path / "rehearsal.db"

    result = _run(["--snapshot", str(tmp_path / "nope.db"), "--target", str(target)])

    assert result.returncode == 1
    assert result.stdout == ""
    assert "restore failed:" in result.stderr
    assert not target.exists()


def test_cli_refuses_existing_target(tmp_path: Path) -> None:
    snapshot = tmp_path / "snap.db"
    _recipe_shaped_sqlite(snapshot)
    target = tmp_path / "occupied.db"
    target.write_bytes(b"keep me")

    result = _run(["--snapshot", str(snapshot), "--target", str(target)])

    assert result.returncode == 1
    assert "restore failed:" in result.stderr
    assert "already exists" in result.stderr
    assert target.read_bytes() == b"keep me"


def test_cli_rejects_invalid_snapshot(tmp_path: Path) -> None:
    junk = tmp_path / "junk.db"
    junk.write_bytes(b"nope" * 100)
    target = tmp_path / "rehearsal.db"

    result = _run(["--snapshot", str(junk), "--target", str(target)])

    assert result.returncode == 1
    assert "restore failed:" in result.stderr
    assert not target.exists()
