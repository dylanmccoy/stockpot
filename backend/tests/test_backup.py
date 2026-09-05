"""Live SQLite snapshot behavior (private-household-deployment ticket 02a).

Uses real file-backed SQLite databases and the production app factory —
`conftest.py`'s shared fixtures are in-memory, which can't be file-copied, so
this module builds its own file-backed app/engine per test.
"""

import os
import sqlite3
import stat
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.backup
from app.backup import BackupError, create_backup
from app.config import Settings
from app.database import make_engine
from app.main import create_app

REGISTRATION_CODE = "backup-test-registration-code"
USERNAME = "backup-tester"
PASSWORD = "correct horse battery staple"


def _file_settings(db_path: Path, *, allow_registration: bool) -> Settings:
    return Settings(
        database_url=f"sqlite:///{db_path}",
        allow_registration=allow_registration,
        registration_code=REGISTRATION_CODE,
    )


def _make_plain_sqlite_file(path: Path) -> None:
    """A minimal real SQLite file, for tests that don't need the app schema."""
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()


def test_create_backup_round_trips_through_app_factory(tmp_path: Path) -> None:
    """The documented recovery path: seed through real APIs, back up while the
    app is live, then open the snapshot with a fresh app factory and read the
    same records back through fresh login."""
    live_db = tmp_path / "live.db"
    dest_dir = tmp_path / "backups"

    live_engine = make_engine(f"sqlite:///{live_db}")
    live_app = create_app(_file_settings(live_db, allow_registration=True), live_engine)
    with TestClient(live_app) as client:
        register = client.post(
            "/api/auth/register",
            json={"username": USERNAME, "password": PASSWORD, "code": REGISTRATION_CODE},
        )
        assert register.status_code == 201, register.text
        login = client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
        assert login.status_code == 200, login.text
        client.headers["Authorization"] = f"Bearer {login.json()['token']}"

        created = client.post(
            "/api/recipes",
            json={"title": "Snapshot Pancakes", "tags": [], "steps": [], "ingredients": []},
        )
        assert created.status_code == 201, created.text

        # The app is still open (live_engine's connection pool is warm) when
        # the backup runs, per the "no planned outage" requirement.
        snapshot_path = create_backup(live_db, dest_dir)

    assert snapshot_path.parent == dest_dir
    assert snapshot_path.is_file()

    snapshot_engine = make_engine(f"sqlite:///{snapshot_path}")
    snapshot_app = create_app(
        _file_settings(snapshot_path, allow_registration=False), snapshot_engine
    )
    with TestClient(snapshot_app) as client:
        login = client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
        assert login.status_code == 200, login.text
        client.headers["Authorization"] = f"Bearer {login.json()['token']}"

        listed = client.get("/api/recipes")
        assert listed.status_code == 200
        titles = [r["title"] for r in listed.json()]
        assert "Snapshot Pancakes" in titles


def test_missing_source_fails_without_touching_destination(tmp_path: Path) -> None:
    missing = tmp_path / "nope.db"
    dest_dir = tmp_path / "backups"

    with pytest.raises(BackupError, match="source database not found"):
        create_backup(missing, dest_dir)

    assert not dest_dir.exists()


def test_unwritable_destination_fails_and_creates_no_snapshot(tmp_path: Path) -> None:
    if os.geteuid() == 0:
        pytest.skip("permission bits are not enforced for root")

    source = tmp_path / "live.db"
    _make_plain_sqlite_file(source)

    # A read-only parent, not a self-chmod'd dest_dir: `create_backup` always
    # re-tightens a dest_dir it can already reach to 0700 (as owner, chmod
    # succeeds regardless of the directory's prior mode), so the only way to
    # keep it genuinely unreachable is to block the `mkdir` that gets there.
    readonly_parent = tmp_path / "readonly-parent"
    readonly_parent.mkdir()
    readonly_parent.chmod(0o500)  # read + execute, no write
    dest_dir = readonly_parent / "backups"
    try:
        with pytest.raises(BackupError):
            create_backup(source, dest_dir)
    finally:
        readonly_parent.chmod(0o700)  # let pytest clean up tmp_path

    assert not dest_dir.exists()


def test_interrupted_write_preserves_earlier_snapshot(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "live.db"
    _make_plain_sqlite_file(source)
    dest_dir = tmp_path / "backups"

    first = create_backup(source, dest_dir, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    first_bytes = first.read_bytes()
    first_mtime = first.stat().st_mtime

    def _boom(source: Path, tmp_path: Path) -> None:
        raise sqlite3.OperationalError("simulated interruption")

    monkeypatch.setattr(app.backup, "_run_online_backup", _boom)

    with pytest.raises(BackupError, match="simulated interruption"):
        create_backup(source, dest_dir, now=datetime(2026, 1, 2, tzinfo=timezone.utc))

    remaining = sorted(p.name for p in dest_dir.iterdir())
    assert remaining == [first.name], "interrupted attempt must leave no new/partial file"
    assert first.read_bytes() == first_bytes
    assert first.stat().st_mtime == first_mtime


def test_successive_backups_get_distinct_timestamped_names(tmp_path: Path) -> None:
    source = tmp_path / "live.db"
    _make_plain_sqlite_file(source)
    dest_dir = tmp_path / "backups"

    first = create_backup(source, dest_dir, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    second = create_backup(source, dest_dir, now=datetime(2026, 1, 2, tzinfo=timezone.utc))

    assert first != second
    assert sorted(p.name for p in dest_dir.iterdir()) == sorted([first.name, second.name])


def test_snapshot_and_destination_are_operator_only(tmp_path: Path) -> None:
    if os.geteuid() == 0:
        pytest.skip("permission bits are not enforced for root")

    source = tmp_path / "live.db"
    _make_plain_sqlite_file(source)
    dest_dir = tmp_path / "backups"

    snapshot = create_backup(source, dest_dir)

    dest_mode = stat.S_IMODE(dest_dir.stat().st_mode)
    snapshot_mode = stat.S_IMODE(snapshot.stat().st_mode)
    assert dest_mode == 0o700
    assert snapshot_mode == 0o600


def test_pre_existing_lax_destination_gets_tightened(tmp_path: Path) -> None:
    """A dest_dir left at looser-than-operator-only permissions (e.g. default
    umask, or loosened after the fact) gets tightened back up on every run,
    not just when `create_backup` creates it fresh."""
    if os.geteuid() == 0:
        pytest.skip("permission bits are not enforced for root")

    source = tmp_path / "live.db"
    _make_plain_sqlite_file(source)
    dest_dir = tmp_path / "backups"
    dest_dir.mkdir(mode=0o755)

    create_backup(source, dest_dir)

    assert stat.S_IMODE(dest_dir.stat().st_mode) == 0o700
