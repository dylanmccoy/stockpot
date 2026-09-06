"""In-place database replacement with writers stopped (private-household-deployment
ticket 02c).

Real file-backed SQLite, the production app factory, and the real
`create_backup` snapshot path. Each test seeds a live database through the
API, snapshots it, diverges the live database, then replaces it in place with
`replace_database` and confirms — through a *fresh* factory app on the same
path — that the household is back to the snapshot's world, that the database
that was replaced was preserved, and that a failed step never destroys the
usable target.
"""

import os
import sqlite3
import stat
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import restore
from app.backup import create_backup
from app.config import Settings
from app.database import make_engine
from app.main import create_app
from app.restore import RestoreError, replace_database

REGISTRATION_CODE = "replace-test-registration-code"
USERNAME = "replace-tester"
PASSWORD = "correct horse battery staple"


def _settings(db_path: Path, *, allow_registration: bool) -> Settings:
    return Settings(
        database_url=f"sqlite:///{db_path}",
        allow_registration=allow_registration,
        registration_code=REGISTRATION_CODE,
    )


def _client(db_path: Path, *, allow_registration: bool = False) -> TestClient:
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


def _add_recipe(db_path: Path, token: str, title: str) -> None:
    with _client(db_path) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        made = client.post(
            "/api/recipes",
            json={"title": title, "tags": [], "steps": [], "ingredients": []},
        )
        assert made.status_code == 201, made.text


def _titles_after_fresh_login(db_path: Path) -> list[str]:
    with _client(db_path) as client:
        login = client.post(
            "/api/auth/login", json={"username": USERNAME, "password": PASSWORD}
        )
        assert login.status_code == 200, login.text
        client.headers["Authorization"] = f"Bearer {login.json()['token']}"
        return [r["title"] for r in client.get("/api/recipes").json()]


def _session_count(db_path: Path) -> int:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return conn.execute("SELECT count(*) FROM sessions").fetchone()[0]
    finally:
        conn.close()


def test_replaces_live_database_with_the_snapshot_world(tmp_path: Path) -> None:
    live_db = tmp_path / "recipe.db"
    token = _seed_live_db(live_db)
    snapshot = create_backup(live_db, tmp_path / "backups")

    _add_recipe(live_db, token, "Post-snapshot Pie")  # diverge after the snapshot

    result = replace_database(snapshot, live_db, preserve_dir=tmp_path / "pre-restore")
    assert result.target == live_db
    assert result.preserved.is_file()

    titles = _titles_after_fresh_login(live_db)
    assert "Pre-snapshot Stew" in titles
    assert "Post-snapshot Pie" not in titles


def test_preserved_copy_is_the_database_that_was_replaced(tmp_path: Path) -> None:
    live_db = tmp_path / "recipe.db"
    token = _seed_live_db(live_db)
    snapshot = create_backup(live_db, tmp_path / "backups")
    _add_recipe(live_db, token, "Post-snapshot Pie")

    result = replace_database(snapshot, live_db, preserve_dir=tmp_path / "pre-restore")

    # The live path now lacks the divergence...
    assert "Post-snapshot Pie" not in _titles_after_fresh_login(live_db)
    # ...but the preserved copy is exactly what we replaced, divergence and all.
    assert "Post-snapshot Pie" in _titles_after_fresh_login(result.preserved)


def test_the_snapshots_credential_is_what_is_served_after_replacement(
    tmp_path: Path,
) -> None:
    live_db = tmp_path / "recipe.db"
    token = _seed_live_db(live_db)
    snapshot = create_backup(live_db, tmp_path / "backups")

    # After the snapshot, the member rotates their password on the live DB.
    later_password = "a totally different passphrase"
    with _client(live_db) as client:
        changed = client.post(
            "/api/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": PASSWORD, "new_password": later_password},
        )
        assert changed.status_code == 200, changed.text

    replace_database(snapshot, live_db, preserve_dir=tmp_path / "pre-restore")

    with _client(live_db) as client:
        # The snapshot-era password authenticates; the post-snapshot one does not.
        good = client.post(
            "/api/auth/login", json={"username": USERNAME, "password": PASSWORD}
        )
        assert good.status_code == 200, good.text
        client.headers["Authorization"] = f"Bearer {good.json()['token']}"
        assert client.get("/api/auth/me").json()["username"] == USERNAME

        stale = client.post(
            "/api/auth/login",
            json={"username": USERNAME, "password": later_password},
        )
        assert stale.status_code == 401


def test_restored_sessions_are_invalidated_before_service_resumes(tmp_path: Path) -> None:
    live_db = tmp_path / "recipe.db"
    keep_token = _seed_live_db(live_db)

    with _client(live_db) as client:
        second = client.post(
            "/api/auth/login", json={"username": USERNAME, "password": PASSWORD}
        )
        assert second.status_code == 200, second.text
        revoked_token = second.json()["token"]
        signed_out = client.post(
            "/api/auth/logout", headers={"Authorization": f"Bearer {revoked_token}"}
        )
        assert signed_out.status_code == 204

    snapshot = create_backup(live_db, tmp_path / "backups")
    assert _session_count(snapshot) >= 1  # keep_token is live in the snapshot

    replace_database(snapshot, live_db, preserve_dir=tmp_path / "pre-restore")

    assert _session_count(live_db) == 0
    with _client(live_db) as client:
        for token in (keep_token, revoked_token):
            refused = client.get(
                "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
            )
            assert refused.status_code == 401
        login = client.post(
            "/api/auth/login", json={"username": USERNAME, "password": PASSWORD}
        )
        assert login.status_code == 200, login.text


def test_replaced_database_is_operator_only(tmp_path: Path) -> None:
    if os.geteuid() == 0:
        pytest.skip("permission bits are not enforced for root")

    live_db = tmp_path / "recipe.db"
    _seed_live_db(live_db)
    snapshot = create_backup(live_db, tmp_path / "backups")

    replace_database(snapshot, live_db, preserve_dir=tmp_path / "pre-restore")

    assert stat.S_IMODE(live_db.stat().st_mode) == 0o600


def test_earlier_snapshots_and_the_source_snapshot_are_untouched(tmp_path: Path) -> None:
    live_db = tmp_path / "recipe.db"
    _seed_live_db(live_db)
    snapshot = create_backup(live_db, tmp_path / "backups")

    preserve_dir = tmp_path / "pre-restore"
    preserve_dir.mkdir()
    earlier = preserve_dir / "recipe-20200101T000000Z.db"
    earlier.write_bytes(b"an earlier recovery point")
    earlier_before = earlier.read_bytes()
    snapshot_before = snapshot.read_bytes()

    result = replace_database(snapshot, live_db, preserve_dir=preserve_dir)

    assert earlier.read_bytes() == earlier_before
    assert snapshot.read_bytes() == snapshot_before
    assert result.preserved != earlier
    assert result.preserved.parent == preserve_dir


def test_refuses_when_target_does_not_exist(tmp_path: Path) -> None:
    live_db = tmp_path / "recipe.db"
    _seed_live_db(live_db)
    snapshot = create_backup(live_db, tmp_path / "backups")

    preserve_dir = tmp_path / "pre-restore"
    with pytest.raises(RestoreError, match="not found"):
        replace_database(snapshot, tmp_path / "nope.db", preserve_dir=preserve_dir)

    assert not (tmp_path / "nope.db").exists()
    assert not preserve_dir.exists()  # nothing preserved for a target that isn't there


def test_invalid_snapshot_leaves_target_and_takes_no_preservation(tmp_path: Path) -> None:
    live_db = tmp_path / "recipe.db"
    _seed_live_db(live_db)
    live_before = live_db.read_bytes()

    junk = tmp_path / "junk.db"
    junk.write_bytes(b"this is not a database " * 50)
    preserve_dir = tmp_path / "pre-restore"

    with pytest.raises(RestoreError):
        replace_database(junk, live_db, preserve_dir=preserve_dir)

    assert live_db.read_bytes() == live_before
    # Snapshot is validated before anything is preserved.
    assert not preserve_dir.exists()
    assert _titles_after_fresh_login(live_db) == ["Pre-snapshot Stew"]


def test_failed_preservation_leaves_target_intact(tmp_path: Path) -> None:
    live_db = tmp_path / "recipe.db"
    _seed_live_db(live_db)
    snapshot = create_backup(live_db, tmp_path / "backups")
    live_before = live_db.read_bytes()

    # A file where the preserve directory's parent needs to be — create_backup
    # cannot make the directory, so preservation fails.
    blocker = tmp_path / "blocker"
    blocker.write_bytes(b"not a directory")
    preserve_dir = blocker / "pre-restore"

    with pytest.raises(RestoreError, match="preserving the current database"):
        replace_database(snapshot, live_db, preserve_dir=preserve_dir)

    assert live_db.read_bytes() == live_before
    assert _titles_after_fresh_login(live_db) == ["Pre-snapshot Stew"]


def test_failed_preparation_leaves_target_and_keeps_the_preserved_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    live_db = tmp_path / "recipe.db"
    _seed_live_db(live_db)
    snapshot = create_backup(live_db, tmp_path / "backups")
    live_before = live_db.read_bytes()

    def boom(_db_path: Path) -> None:
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(restore, "_invalidate_sessions", boom)

    preserve_dir = tmp_path / "pre-restore"
    with pytest.raises(RestoreError, match="preparing the recovered database"):
        replace_database(snapshot, live_db, preserve_dir=preserve_dir)

    assert live_db.read_bytes() == live_before
    assert _titles_after_fresh_login(live_db) == ["Pre-snapshot Stew"]
    # Preservation ran and its copy is a real recovery point, left in place.
    preserved = list(preserve_dir.glob("recipe-*.db"))
    assert len(preserved) == 1
    assert "Pre-snapshot Stew" in _titles_after_fresh_login(preserved[0])
    # The half-prepared temp file is not left behind next to the live database.
    assert not list(live_db.parent.glob(".*replacing"))


def test_a_corrupt_target_that_cannot_be_preserved_is_not_replaced(tmp_path: Path) -> None:
    live_db = tmp_path / "recipe.db"
    _seed_live_db(live_db)
    good_snapshot = create_backup(live_db, tmp_path / "backups")

    # The live database is now unreadable garbage: preserving it will fail its
    # validation, so replacement must refuse rather than lose an unpreserved DB.
    live_db.write_bytes(b"corrupted beyond recovery " * 100)
    corrupt_before = live_db.read_bytes()

    with pytest.raises(RestoreError):
        replace_database(
            good_snapshot, live_db, preserve_dir=tmp_path / "pre-restore"
        )

    assert live_db.read_bytes() == corrupt_before
