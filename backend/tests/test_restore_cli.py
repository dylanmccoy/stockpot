"""The operator-facing restore CLI (`scripts/restore.py`), run as a subprocess
exactly as root README.md "Restore rehearsal" / "Restore in place" document
it — both the default rehearsal mode and `--replace`."""

import os
import sqlite3
import subprocess
import sys
from importlib import import_module
from pathlib import Path

from app.database import Base, make_engine

import_module("app.models")  # Populates Base.metadata.

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRIPT = BACKEND_DIR / "scripts" / "restore.py"
_SESSION_COLUMNS = "token, user_id, created_at, last_used_at, expires_at"
_SESSION_INSERT = (
    f"INSERT INTO sessions ({_SESSION_COLUMNS}) "
    "VALUES ('stale-token', 1, '2026-01-01 00:00:00', "
    "'2026-01-01 00:00:00', '2099-01-01 00:00:00')"
)


def _recipe_shaped_sqlite(path: Path) -> None:
    """A real file-backed database with the app's full schema and one session
    row, so the CLI's snapshot validation passes and the row proves the
    session wipe ran."""
    engine = make_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()

    conn = sqlite3.connect(path)
    try:
        conn.execute(_SESSION_INSERT)
        conn.commit()
    finally:
        conn.close()


def _run(
    args: list[str], env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=BACKEND_DIR,
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_cli_success_prints_recovered_path_and_clears_sessions(
    tmp_path: Path,
) -> None:
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


def test_cli_missing_snapshot_fails_without_creating_target(
    tmp_path: Path,
) -> None:
    target = tmp_path / "rehearsal.db"
    missing = tmp_path / "nope.db"

    result = _run(["--snapshot", str(missing), "--target", str(target)])

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


def test_cli_replace_swaps_existing_target_and_preserves_the_prior_database(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "snap.db"
    _recipe_shaped_sqlite(snapshot)
    target = tmp_path / "recipe.db"
    _recipe_shaped_sqlite(target)
    preserve_dir = tmp_path / "pre-restore"

    result = _run(
        [
            "--replace",
            "--snapshot",
            str(snapshot),
            "--target",
            str(target),
            "--preserve-dir",
            str(preserve_dir),
        ]
    )

    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines[0] == f"restore ok: replaced {target}"
    assert lines[1].startswith("preserved prior database: ")

    preserved = list(preserve_dir.glob("recipe-*.db"))
    assert len(preserved) == 1
    prior_prefix = "preserved prior database: "
    assert str(preserved[0]) == lines[1].removeprefix(prior_prefix)

    conn = sqlite3.connect(target)
    try:
        assert conn.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
    finally:
        conn.close()


def test_cli_replace_requires_preserve_dir(tmp_path: Path) -> None:
    snapshot = tmp_path / "snap.db"
    _recipe_shaped_sqlite(snapshot)
    target = tmp_path / "recipe.db"
    _recipe_shaped_sqlite(target)
    target_before = target.read_bytes()

    args = ["--replace", "--snapshot", str(snapshot), "--target", str(target)]
    result = _run(args)

    assert result.returncode != 0
    assert "--preserve-dir" in result.stderr
    assert target.read_bytes() == target_before


def test_cli_replace_refuses_a_missing_target(tmp_path: Path) -> None:
    snapshot = tmp_path / "snap.db"
    _recipe_shaped_sqlite(snapshot)
    preserve_dir = tmp_path / "pre-restore"

    result = _run(
        [
            "--replace",
            "--snapshot",
            str(snapshot),
            "--target",
            str(tmp_path / "nope.db"),
            "--preserve-dir",
            str(preserve_dir),
        ]
    )

    assert result.returncode == 1
    assert "restore failed:" in result.stderr
    assert not (tmp_path / "nope.db").exists()
    assert not preserve_dir.exists()


def test_cli_replace_rejects_invalid_snapshot_without_touching_target(
    tmp_path: Path,
) -> None:
    junk = tmp_path / "junk.db"
    junk.write_bytes(b"nope" * 100)
    target = tmp_path / "recipe.db"
    _recipe_shaped_sqlite(target)
    target_before = target.read_bytes()
    preserve_dir = tmp_path / "pre-restore"

    result = _run(
        [
            "--replace",
            "--snapshot",
            str(junk),
            "--target",
            str(target),
            "--preserve-dir",
            str(preserve_dir),
        ]
    )

    assert result.returncode == 1
    assert "restore failed:" in result.stderr
    assert target.read_bytes() == target_before
    assert not preserve_dir.exists()


def test_cli_rejects_preserve_dir_without_replace(tmp_path: Path) -> None:
    snapshot = tmp_path / "snap.db"
    _recipe_shaped_sqlite(snapshot)

    result = _run(
        [
            "--snapshot",
            str(snapshot),
            "--target",
            str(tmp_path / "rehearsal.db"),
            "--preserve-dir",
            str(tmp_path / "pre-restore"),
        ]
    )

    assert result.returncode != 0
    assert "--preserve-dir" in result.stderr
    assert not (tmp_path / "rehearsal.db").exists()
