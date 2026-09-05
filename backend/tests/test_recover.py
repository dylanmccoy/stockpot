"""Forgotten-password recovery (private-household-deployment ticket 03b).

`recover_password` resets one existing household account's password directly
in a stopped deployment's database and revokes that account's sessions. These
tests drive it against disposable file-backed databases and a real factory
app, through the existing authentication API — no mocks, no dependency
overrides.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.database import Base, make_engine
from app.main import create_app
from app.models import Session as SessionModel
from app.models import User
from app.provision import provision_accounts
from app.recover import RecoverError, RecoverResult, recover_password
from app.security import verify_password


def _schema_db(path: Path) -> str:
    """A file-backed SQLite database with the app's full schema and no rows."""
    url = f"sqlite:///{path}"
    engine = make_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    return url


def _closed_client(url: str) -> TestClient:
    """A production-shaped app over `url` with registration closed."""
    settings = Settings(database_url=url, allow_registration=False)
    return TestClient(create_app(settings, make_engine(url)))


def _hash_of(url: str, username: str) -> str:
    engine = make_engine(url)
    try:
        with engine.connect() as conn:
            return conn.execute(
                select(User.password_hash).where(User.username == username)
            ).scalar_one()
    finally:
        engine.dispose()


def _login(client: TestClient, username: str, password: str):
    return client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )


def test_replaces_hash_and_revokes_all_sessions(tmp_path: Path) -> None:
    url = _schema_db(tmp_path / "recipe.db")
    provision_accounts(url, [("alice", "old-passphrase")])

    with _closed_client(url) as c:
        first = _login(c, "alice", "old-passphrase")
        second = _login(c, "alice", "old-passphrase")
    assert first.status_code == 200 and second.status_code == 200

    result = recover_password(url, "alice", "fresh-passphrase")

    assert result == RecoverResult(username="alice", sessions_revoked=2)
    assert verify_password("fresh-passphrase", _hash_of(url, "alice"))
    assert not verify_password("old-passphrase", _hash_of(url, "alice"))

    engine = make_engine(url)
    with engine.connect() as conn:
        assert conn.execute(select(SessionModel)).first() is None
    engine.dispose()


def test_no_sessions_to_revoke_is_fine(tmp_path: Path) -> None:
    url = _schema_db(tmp_path / "recipe.db")
    provision_accounts(url, [("alice", "old-passphrase")])

    result = recover_password(url, "alice", "fresh-passphrase")

    assert result == RecoverResult(username="alice", sessions_revoked=0)


def test_username_match_is_case_insensitive_and_stored_casing_kept(
    tmp_path: Path,
) -> None:
    url = _schema_db(tmp_path / "recipe.db")
    provision_accounts(url, [("Alice", "old-passphrase")])

    result = recover_password(url, "alice", "fresh-passphrase")

    assert result.username == "Alice"
    assert verify_password("fresh-passphrase", _hash_of(url, "Alice"))


def test_only_the_target_account_is_touched(tmp_path: Path) -> None:
    url = _schema_db(tmp_path / "recipe.db")
    provision_accounts(
        url, [("alice", "alice-passphrase"), ("bob", "bob-passphrase")]
    )

    # Bob has a live session and a household record; recovering Alice must not
    # disturb either.
    with _closed_client(url) as c:
        bob_login = _login(c, "bob", "bob-passphrase")
        assert bob_login.status_code == 200
        bob_token = bob_login.json()["token"]
        bob_h = {"Authorization": f"Bearer {bob_token}"}
        made = c.post("/api/recipes", json={"title": "Bob's Loaf"}, headers=bob_h)
        assert made.status_code == 201, made.text
        recipe_id = made.json()["id"]

    bob_hash_before = _hash_of(url, "bob")

    recover_password(url, "alice", "fresh-passphrase")

    assert _hash_of(url, "bob") == bob_hash_before
    with _closed_client(url) as c:
        bob_h = {"Authorization": f"Bearer {bob_token}"}
        assert c.get("/api/auth/me", headers=bob_h).status_code == 200
        got = c.get(f"/api/recipes/{recipe_id}", headers=bob_h)
        assert got.status_code == 200
        assert got.json()["title"] == "Bob's Loaf"


def test_unknown_account_is_refused_and_creates_nothing(tmp_path: Path) -> None:
    url = _schema_db(tmp_path / "recipe.db")
    provision_accounts(url, [("alice", "alice-passphrase")])

    with pytest.raises(RecoverError, match="no such account"):
        recover_password(url, "mallory", "fresh-passphrase")

    engine = make_engine(url)
    with engine.connect() as conn:
        names = conn.execute(select(User.username)).scalars().all()
    engine.dispose()
    assert names == ["alice"]
    assert verify_password("alice-passphrase", _hash_of(url, "alice"))


@pytest.mark.parametrize("bad_password", ["short", "x" * 200])
def test_invalid_password_is_refused_and_changes_nothing(
    tmp_path: Path, bad_password: str
) -> None:
    url = _schema_db(tmp_path / "recipe.db")
    provision_accounts(url, [("alice", "alice-passphrase")])
    before = _hash_of(url, "alice")

    with pytest.raises(RecoverError, match="invalid recovery input"):
        recover_password(url, "alice", bad_password)

    assert _hash_of(url, "alice") == before


def test_missing_database_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RecoverError, match="not found"):
        recover_password(
            f"sqlite:///{tmp_path / 'absent.db'}", "alice", "fresh-passphrase"
        )


def test_database_without_schema_is_refused(tmp_path: Path) -> None:
    import sqlite3

    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    with pytest.raises(RecoverError, match="no schema"):
        recover_password(f"sqlite:///{empty}", "alice", "fresh-passphrase")


def test_recovered_member_logs_in_fresh_while_old_credentials_and_tokens_fail(
    tmp_path: Path,
) -> None:
    """Ticket crit 2, through the real auth API: after recovery the old
    password and old session token both fail and the new password works, while
    another member and the household records are untouched."""
    url = _schema_db(tmp_path / "recipe.db")
    provision_accounts(
        url, [("alice", "old-passphrase"), ("bob", "bob-passphrase")]
    )

    with _closed_client(url) as c:
        alice_login = _login(c, "alice", "old-passphrase")
        assert alice_login.status_code == 200
        alice_token = alice_login.json()["token"]
        made = c.post(
            "/api/recipes",
            json={"title": "Household Loaf"},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert made.status_code == 201, made.text
        recipe_id = made.json()["id"]

    result = recover_password(url, "alice", "new-passphrase")
    assert result == RecoverResult(username="alice", sessions_revoked=1)

    with _closed_client(url) as c:
        # Old session token: dead.
        stale = c.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {alice_token}"}
        )
        assert stale.status_code == 401

        # Old password: rejected.
        assert _login(c, "alice", "old-passphrase").status_code == 401

        # New password: works, and sees the same household record.
        fresh = _login(c, "alice", "new-passphrase")
        assert fresh.status_code == 200, fresh.text
        fresh_h = {"Authorization": f"Bearer {fresh.json()['token']}"}
        got = c.get(f"/api/recipes/{recipe_id}", headers=fresh_h)
        assert got.status_code == 200
        assert got.json()["title"] == "Household Loaf"

        # The other member is unaffected.
        assert _login(c, "bob", "bob-passphrase").status_code == 200
