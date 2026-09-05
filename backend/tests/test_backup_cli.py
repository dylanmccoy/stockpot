"""The operator-facing CLI wrapper (`scripts/backup.py`), invoked exactly as
documented in root README.md "Backup" — as a subprocess, not by importing its
`main()`, so these tests exercise the actual command an operator runs."""

import os
import subprocess
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRIPT = BACKEND_DIR / "scripts" / "backup.py"


def _make_plain_sqlite_file(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()


def _run(args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    full_env = {**os.environ, **(env or {})}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=BACKEND_DIR,
        env=full_env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_cli_success_prints_snapshot_path(tmp_path: Path) -> None:
    source = tmp_path / "live.db"
    _make_plain_sqlite_file(source)
    dest_dir = tmp_path / "backups"

    result = _run(["--source", str(source), "--dest-dir", str(dest_dir)])

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("backup ok: ")
    snapshot = Path(result.stdout.removeprefix("backup ok: ").strip())
    assert snapshot.is_file()
    assert snapshot.parent == dest_dir


def test_cli_missing_source_fails_with_stderr_and_no_output_file(tmp_path: Path) -> None:
    missing = tmp_path / "nope.db"
    dest_dir = tmp_path / "backups"

    result = _run(["--source", str(missing), "--dest-dir", str(dest_dir)])

    assert result.returncode == 1
    assert result.stdout == ""
    assert "backup failed:" in result.stderr
    assert not dest_dir.exists()


def test_cli_defaults_source_to_recipe_database_url(tmp_path: Path) -> None:
    source = tmp_path / "live.db"
    _make_plain_sqlite_file(source)
    dest_dir = tmp_path / "backups"

    result = _run(["--dest-dir", str(dest_dir)], env={"RECIPE_DATABASE_URL": f"sqlite:///{source}"})

    assert result.returncode == 0, result.stderr
    assert list(dest_dir.glob("recipe-*.db"))


def test_cli_rejects_non_file_backed_database_url(tmp_path: Path) -> None:
    dest_dir = tmp_path / "backups"

    result = _run(
        ["--dest-dir", str(dest_dir)],
        env={"RECIPE_DATABASE_URL": "postgresql://localhost/recipe"},
    )

    assert result.returncode == 1
    assert "backup failed:" in result.stderr
    assert "sqlite:///" in result.stderr
    assert not dest_dir.exists()
