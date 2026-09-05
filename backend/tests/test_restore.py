"""Isolated recovery-rehearsal behavior (private-household-deployment ticket 02b).

Real file-backed SQLite, the production app factory, and the real
`create_backup` snapshot path — recovery is only meaningful end to end: seed a
live database, snapshot it, diverge the live database, recover the snapshot
into a throwaway target, and confirm a fresh app on that target sees the
snapshot's world and not the later divergence.
"""

import os
import sqlite3
import stat
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.backup import create_backup
from app.config import Settings
from app.database import make_engine
from app.main import create_app
from app.restore import RestoreError, recover_snapshot

REGISTRATION_CODE = "restore-test-registration-code"
USERNAME = "restore-tester"
PASSWORD = "correct horse battery staple"


def _settings(db_path: Path, *, allow_registration: bool) -> Settings:
    return Settings(
        database_url=f"sqlite:///{db_path}",
        allow_registration=allow_registration,
        registration_code=REGISTRATION_CODE,
    )


def _client(db_path: Path, *, allow_registration: bool) -> TestClient:
    engine = make_engine(f"sqlite:///{db_path}")
    return TestClient(
        create_app(_settings(db_path, allow_registration=allow_registration), engine)
    )


def _seed_live_db(db_path: Path) -> str:
    """Register + log in one user and create one recipe. Returns the token."""
    with _client(db_path, allow_registration=True) as client:
        registered = client.post(
            "/api/auth/register",
            json={"username": USERNAME, "password": PASSWORD, "code": REGISTRATION_CODE},
        )
        assert registered.status_code == 201, registered.text
        token = registered.json()["token"]
        client.headers["Authorization"] = f"Bearer {token}"
        made = client.post(
            "/api/recipes",
            json={"title": "Pre-snapshot Stew", "tags": [], "steps": [], "ingredients": []},
        )
        assert made.status_code == 201, made.text
    return token


def _session_count(db_path: Path) -> int:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return conn.execute("SELECT count(*) FROM sessions").fetchone()[0]
    finally:
        conn.close()


def test_recovers_snapshot_world_without_later_changes(tmp_path: Path) -> None:
    live_db = tmp_path / "live.db"
    token = _seed_live_db(live_db)

    snapshot = create_backup(live_db, tmp_path / "backups")

    # Diverge the live database after the snapshot was taken.
    with _client(live_db, allow_registration=False) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        later = client.post(
            "/api/recipes",
            json={"title": "Post-snapshot Pie", "tags": [], "steps": [], "ingredients": []},
        )
        assert later.status_code == 201, later.text

    target = tmp_path / "rehearsal.db"
    recovered = recover_snapshot(snapshot, target)
    assert recovered == target
    assert target.is_file()

    with _client(target, allow_registration=False) as client:
        login = client.post(
            "/api/auth/login", json={"username": USERNAME, "password": PASSWORD}
        )
        assert login.status_code == 200, login.text
        client.headers["Authorization"] = f"Bearer {login.json()['token']}"
        titles = [r["title"] for r in client.get("/api/recipes").json()]

    assert "Pre-snapshot Stew" in titles
    assert "Post-snapshot Pie" not in titles


def test_recovered_database_refuses_snapshot_session_tokens(tmp_path: Path) -> None:
    live_db = tmp_path / "live.db"
    snapshot_token = _seed_live_db(live_db)
    snapshot = create_backup(live_db, tmp_path / "backups")

    # The token really is live in the snapshot as taken...
    assert _session_count(snapshot) >= 1

    target = tmp_path / "rehearsal.db"
    recover_snapshot(snapshot, target)

    # ...and gone from the recovered database before it is ever served.
    assert _session_count(target) == 0

    with _client(target, allow_registration=False) as client:
        refused = client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {snapshot_token}"}
        )
        assert refused.status_code == 401

        login = client.post(
            "/api/auth/login", json={"username": USERNAME, "password": PASSWORD}
        )
        assert login.status_code == 200, login.text
        fresh = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {login.json()['token']}"},
        )
        assert fresh.status_code == 200
        assert fresh.json()["username"] == USERNAME


def test_live_database_and_snapshot_are_untouched_by_recovery(tmp_path: Path) -> None:
    live_db = tmp_path / "live.db"
    _seed_live_db(live_db)
    snapshot = create_backup(live_db, tmp_path / "backups")

    live_before = live_db.read_bytes()
    snapshot_before = snapshot.read_bytes()

    recover_snapshot(snapshot, tmp_path / "rehearsal.db")

    assert live_db.read_bytes() == live_before
    assert snapshot.read_bytes() == snapshot_before


def test_refuses_an_existing_target(tmp_path: Path) -> None:
    live_db = tmp_path / "live.db"
    _seed_live_db(live_db)
    snapshot = create_backup(live_db, tmp_path / "backups")

    target = tmp_path / "occupied.db"
    target.write_bytes(b"do not touch")

    with pytest.raises(RestoreError, match="already exists"):
        recover_snapshot(snapshot, target)

    assert target.read_bytes() == b"do not touch"


def test_missing_snapshot_creates_no_target(tmp_path: Path) -> None:
    target = tmp_path / "out.db"

    with pytest.raises(RestoreError, match="snapshot not found"):
        recover_snapshot(tmp_path / "nope.db", target)

    assert not target.exists()


def test_garbage_snapshot_creates_no_target(tmp_path: Path) -> None:
    junk = tmp_path / "junk.db"
    junk.write_bytes(b"this is not a database " * 50)
    target = tmp_path / "out.db"

    with pytest.raises(RestoreError):
        recover_snapshot(junk, target)

    assert not target.exists()


def test_valid_sqlite_that_is_not_a_recipe_database_is_rejected(tmp_path: Path) -> None:
    other = tmp_path / "other.db"
    conn = sqlite3.connect(other)
    conn.execute("CREATE TABLE widgets (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    target = tmp_path / "out.db"

    with pytest.raises(RestoreError, match="not a recipe-app database"):
        recover_snapshot(other, target)

    assert not target.exists()


def test_recovered_database_is_operator_only(tmp_path: Path) -> None:
    if os.geteuid() == 0:
        pytest.skip("permission bits are not enforced for root")

    live_db = tmp_path / "live.db"
    _seed_live_db(live_db)
    snapshot = create_backup(live_db, tmp_path / "backups")

    target = tmp_path / "rehearsal.db"
    recover_snapshot(snapshot, target)

    assert stat.S_IMODE(target.stat().st_mode) == 0o600
