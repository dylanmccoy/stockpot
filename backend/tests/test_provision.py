"""Household account provisioning (private-household-deployment ticket 03a).

`provision_accounts` creates the intended household logins directly in a
stopped deployment's database, then the deployment runs with registration
closed. These tests drive that path against disposable file-backed databases
and a real factory app — no mocks, no dependency overrides.
"""

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.database import Base, make_engine
from app.main import create_app
from app.models import Session as SessionModel
from app.models import User
from app.provision import ProvisionError, ProvisionResult, provision_accounts
from app.security import verify_password


def _schema_db(path: Path) -> str:
    """A file-backed SQLite database with the app's full schema and no rows —
    what a deployment's database looks like before its first account."""
    url = f"sqlite:///{path}"
    engine = make_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    return url


def _closed_client(url: str) -> TestClient:
    """A production-shaped app over `url` with registration closed."""
    settings = Settings(database_url=url, allow_registration=False)
    return TestClient(create_app(settings, make_engine(url)))


def test_creates_a_login_per_account(tmp_path: Path) -> None:
    url = _schema_db(tmp_path / "recipe.db")

    result = provision_accounts(url, [("alice", "alice-passphrase"), ("bob", "bob-passphrase")])

    assert result == ProvisionResult(created=["alice", "bob"], skipped=[])

    engine = make_engine(url)
    with engine.connect() as conn:
        rows = conn.execute(select(User.username, User.password_hash)).all()
    engine.dispose()

    by_name = {u: h for u, h in rows}
    assert set(by_name) == {"alice", "bob"}
    # Stored as a real argon2 hash the login path can verify — not the plaintext.
    assert verify_password("alice-passphrase", by_name["alice"])
    assert "alice-passphrase" not in by_name["alice"]


def test_no_session_is_issued(tmp_path: Path) -> None:
    url = _schema_db(tmp_path / "recipe.db")

    provision_accounts(url, [("alice", "alice-passphrase")])

    engine = make_engine(url)
    with engine.connect() as conn:
        assert conn.execute(select(SessionModel)).first() is None
    engine.dispose()


def test_existing_username_is_skipped_not_duplicated(tmp_path: Path) -> None:
    url = _schema_db(tmp_path / "recipe.db")
    provision_accounts(url, [("Alice", "alice-passphrase")])

    # Re-run with a case-variant of an existing member plus a new one.
    result = provision_accounts(url, [("alice", "different-passphrase"), ("bob", "bob-passphrase")])

    assert result == ProvisionResult(created=["bob"], skipped=["Alice"])

    engine = make_engine(url)
    with engine.connect() as conn:
        names = conn.execute(select(User.username)).scalars().all()
        alice_hash = conn.execute(
            select(User.password_hash).where(User.username == "Alice")
        ).scalar_one()
    engine.dispose()

    assert sorted(names) == ["Alice", "bob"]
    # The skipped account keeps its original password.
    assert verify_password("alice-passphrase", alice_hash)


def test_empty_list_is_a_noop(tmp_path: Path) -> None:
    url = _schema_db(tmp_path / "recipe.db")
    assert provision_accounts(url, []) == ProvisionResult()


def test_missing_database_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ProvisionError, match="not found"):
        provision_accounts(
            f"sqlite:///{tmp_path / 'absent.db'}", [("alice", "alice-passphrase")]
        )


def test_database_without_schema_is_refused(tmp_path: Path) -> None:
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()  # a real SQLite file, but with no tables
    with pytest.raises(ProvisionError, match="no schema"):
        provision_accounts(f"sqlite:///{empty}", [("alice", "alice-passphrase")])


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("ab", "long-enough-passphrase"),  # username too short for the register rule
        ("has space", "long-enough-passphrase"),  # username charset
        ("alice", "short"),  # password below 8 chars
    ],
)
def test_invalid_account_is_refused_and_commits_nothing(
    tmp_path: Path, username: str, password: str
) -> None:
    url = _schema_db(tmp_path / "recipe.db")

    with pytest.raises(ProvisionError):
        provision_accounts(url, [("valid", "valid-passphrase"), (username, password)])

    engine = make_engine(url)
    with engine.connect() as conn:
        assert conn.execute(select(User)).first() is None
    engine.dispose()


def test_list_repeating_a_username_is_refused(tmp_path: Path) -> None:
    url = _schema_db(tmp_path / "recipe.db")
    with pytest.raises(ProvisionError, match="repeats a username"):
        provision_accounts(url, [("alice", "passphrase-one"), ("Alice", "passphrase-two")])


def test_two_provisioned_members_share_read_write_and_registration_is_closed(
    tmp_path: Path,
) -> None:
    """Spec docs/spec.md decision 8 + "Serving and authentication cases": two
    individual accounts have equal read/write on the same household records,
    and a direct registration request is refused once the deployment runs."""
    url = _schema_db(tmp_path / "recipe.db")
    provision_accounts(url, [("alice", "alice-passphrase"), ("bob", "bob-passphrase")])

    client = _closed_client(url)
    with client:
        alice = client.post(
            "/api/auth/login", json={"username": "alice", "password": "alice-passphrase"}
        )
        bob = client.post(
            "/api/auth/login", json={"username": "bob", "password": "bob-passphrase"}
        )
        assert alice.status_code == 200, alice.text
        assert bob.status_code == 200, bob.text
        alice_h = {"Authorization": f"Bearer {alice.json()['token']}"}
        bob_h = {"Authorization": f"Bearer {bob.json()['token']}"}

        created = client.post("/api/recipes", json={"title": "Shared Loaf"}, headers=alice_h)
        assert created.status_code == 201, created.text
        recipe_id = created.json()["id"]

        # Bob reads Alice's record and edits it.
        assert client.get(f"/api/recipes/{recipe_id}", headers=bob_h).status_code == 200
        edited = client.put(
            f"/api/recipes/{recipe_id}", json={"title": "Shared Loaf (Bob's edit)"}, headers=bob_h
        )
        assert edited.status_code == 200, edited.text

        # Alice sees Bob's edit on the same record.
        seen = client.get(f"/api/recipes/{recipe_id}", headers=alice_h)
        assert seen.status_code == 200
        assert seen.json()["title"] == "Shared Loaf (Bob's edit)"

        # Registration is closed on the running deployment.
        refused = client.post(
            "/api/auth/register",
            json={"username": "gatecrasher", "password": "another-passphrase"},
        )
        assert refused.status_code == 403
        assert refused.json() == {"detail": "registration disabled"}


def test_registration_open_then_refused_after_closure(tmp_path: Path) -> None:
    """Ticket crit 1/2: the closure is a real transition, not a constant —
    the same provisioned database serves `register` while the window is open
    and refuses it once the deployment runs with it closed."""
    url = _schema_db(tmp_path / "recipe.db")
    provision_accounts(url, [("alice", "alice-passphrase")])

    open_settings = Settings(
        database_url=url, allow_registration=True, registration_code="transition-code"
    )
    with TestClient(create_app(open_settings, make_engine(url))) as c:
        opened = c.post(
            "/api/auth/register",
            json={
                "username": "late",
                "password": "late-passphrase",
                "code": "transition-code",
            },
        )
        assert opened.status_code == 201, opened.text

    with _closed_client(url) as c:
        closed = c.post(
            "/api/auth/register",
            json={"username": "later", "password": "later-passphrase"},
        )
        assert closed.status_code == 403
        assert closed.json() == {"detail": "registration disabled"}
