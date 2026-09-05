"""The operator-facing recovery CLI (`scripts/recover.py`), run as a subprocess
exactly as root README.md "Household password recovery" documents it."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.database import Base, make_engine
from app.main import create_app
from app.provision import provision_accounts

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRIPT = BACKEND_DIR / "scripts" / "recover.py"


def _schema_db(path: Path) -> str:
    url = f"sqlite:///{path}"
    engine = make_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    return url


def _run(
    args: list[str], env: dict[str, str] | None = None, stdin: str | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=BACKEND_DIR,
        env={**os.environ, **(env or {})},
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _login(url: str, username: str, password: str) -> int:
    with TestClient(
        create_app(Settings(database_url=url, allow_registration=False), make_engine(url))
    ) as c:
        return c.post(
            "/api/auth/login", json={"username": username, "password": password}
        ).status_code


def test_cli_recovers_revokes_sessions_and_never_echoes_the_password(
    tmp_path: Path,
) -> None:
    url = _schema_db(tmp_path / "recipe.db")
    provision_accounts(url, [("alice", "old-secret-passphrase")])
    assert _login(url, "alice", "old-secret-passphrase") == 200  # one live session

    pw_file = tmp_path / "new-password.txt"
    pw_file.write_text("new-secret-passphrase\n")

    result = _run(["--username", "alice", "--password-file", str(pw_file), "--database-url", url])

    assert result.returncode == 0, result.stderr
    assert "recovered: alice (1 session(s) revoked)" in result.stdout
    assert "secret-passphrase" not in result.stdout
    assert "secret-passphrase" not in result.stderr
    assert _login(url, "alice", "new-secret-passphrase") == 200
    assert _login(url, "alice", "old-secret-passphrase") == 401


def test_cli_reads_password_from_stdin(tmp_path: Path) -> None:
    url = _schema_db(tmp_path / "recipe.db")
    provision_accounts(url, [("alice", "old-secret-passphrase")])

    result = _run(
        ["--username", "alice", "--password-file", "-", "--database-url", url],
        stdin="new-secret-passphrase\n",
    )

    assert result.returncode == 0, result.stderr
    assert _login(url, "alice", "new-secret-passphrase") == 200


def test_cli_defaults_database_url_to_env_and_echoes_it(tmp_path: Path) -> None:
    url = _schema_db(tmp_path / "recipe.db")
    provision_accounts(url, [("alice", "old-secret-passphrase")])
    pw_file = tmp_path / "new-password.txt"
    pw_file.write_text("new-secret-passphrase\n")

    result = _run(
        ["--username", "alice", "--password-file", str(pw_file)],
        env={"RECIPE_DATABASE_URL": url},
    )

    assert result.returncode == 0, result.stderr
    assert f"database: {url}" in result.stdout


def test_cli_refuses_an_unknown_account_and_writes_nothing(tmp_path: Path) -> None:
    url = _schema_db(tmp_path / "recipe.db")
    provision_accounts(url, [("alice", "old-secret-passphrase")])
    pw_file = tmp_path / "new-password.txt"
    pw_file.write_text("new-secret-passphrase\n")

    result = _run(
        ["--username", "mallory", "--password-file", str(pw_file), "--database-url", url]
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "no such account" in result.stderr
    assert _login(url, "alice", "old-secret-passphrase") == 200


def test_cli_refuses_a_short_password(tmp_path: Path) -> None:
    url = _schema_db(tmp_path / "recipe.db")
    provision_accounts(url, [("alice", "old-secret-passphrase")])
    pw_file = tmp_path / "new-password.txt"
    pw_file.write_text("short\n")

    result = _run(
        ["--username", "alice", "--password-file", str(pw_file), "--database-url", url]
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert _login(url, "alice", "old-secret-passphrase") == 200


def test_cli_refuses_an_empty_password_file(tmp_path: Path) -> None:
    url = _schema_db(tmp_path / "recipe.db")
    provision_accounts(url, [("alice", "old-secret-passphrase")])
    pw_file = tmp_path / "new-password.txt"
    pw_file.write_text("\n\n")

    result = _run(
        ["--username", "alice", "--password-file", str(pw_file), "--database-url", url]
    )

    assert result.returncode == 1
    assert "password file is empty" in result.stderr


def test_cli_refuses_a_missing_database_file(tmp_path: Path) -> None:
    pw_file = tmp_path / "new-password.txt"
    pw_file.write_text("new-secret-passphrase\n")

    result = _run(
        [
            "--username",
            "alice",
            "--password-file",
            str(pw_file),
            "--database-url",
            f"sqlite:///{tmp_path / 'absent.db'}",
        ]
    )

    assert result.returncode == 1
    assert "not found" in result.stderr


def test_cli_refuses_a_database_without_schema(tmp_path: Path) -> None:
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    pw_file = tmp_path / "new-password.txt"
    pw_file.write_text("new-secret-passphrase\n")

    result = _run(
        ["--username", "alice", "--password-file", str(pw_file), "--database-url", f"sqlite:///{empty}"]
    )

    assert result.returncode == 1
    assert "no schema" in result.stderr
