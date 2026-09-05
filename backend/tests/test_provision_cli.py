"""The operator-facing provisioning CLI (`scripts/provision.py`), run as a
subprocess exactly as root README.md "Household account provisioning"
documents it."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import select

from app import models  # noqa: F401  — populates Base.metadata
from app.database import Base, make_engine
from app.models import User

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRIPT = BACKEND_DIR / "scripts" / "provision.py"


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


def _usernames(url: str) -> list[str]:
    engine = make_engine(url)
    try:
        with engine.connect() as conn:
            return sorted(conn.execute(select(User.username)).scalars().all())
    finally:
        engine.dispose()


def test_cli_provisions_accounts_and_never_echoes_passwords(tmp_path: Path) -> None:
    db = tmp_path / "recipe.db"
    url = _schema_db(db)
    accounts = tmp_path / "accounts.txt"
    accounts.write_text(
        "# household\nalice alice-secret-passphrase\nbob bob-secret-passphrase\n"
    )

    result = _run(["--accounts", str(accounts), "--database-url", url])

    assert result.returncode == 0, result.stderr
    assert "provisioned: alice, bob" in result.stdout
    assert "returns 403" in result.stdout
    assert "secret-passphrase" not in result.stdout
    assert "secret-passphrase" not in result.stderr
    assert _usernames(url) == ["alice", "bob"]


def test_cli_reads_accounts_from_stdin(tmp_path: Path) -> None:
    url = _schema_db(tmp_path / "recipe.db")

    result = _run(
        ["--accounts", "-", "--database-url", url], stdin="alice alice-secret-passphrase\n"
    )

    assert result.returncode == 0, result.stderr
    assert _usernames(url) == ["alice"]


def test_cli_defaults_database_url_to_env_and_echoes_it(tmp_path: Path) -> None:
    db = tmp_path / "recipe.db"
    url = _schema_db(db)
    accounts = tmp_path / "accounts.txt"
    accounts.write_text("alice alice-secret-passphrase\n")

    result = _run(["--accounts", str(accounts)], env={"RECIPE_DATABASE_URL": url})

    assert result.returncode == 0, result.stderr
    assert f"database: {url}" in result.stdout
    assert _usernames(url) == ["alice"]


def test_cli_rejects_a_malformed_line_and_writes_nothing(tmp_path: Path) -> None:
    url = _schema_db(tmp_path / "recipe.db")
    accounts = tmp_path / "accounts.txt"
    accounts.write_text("alice alice-secret-passphrase\nbob\n")

    result = _run(["--accounts", str(accounts), "--database-url", url])

    assert result.returncode == 1
    assert result.stdout == ""
    assert "line 2" in result.stderr
    assert _usernames(url) == []


def test_cli_reports_already_existing_accounts_as_skipped(tmp_path: Path) -> None:
    url = _schema_db(tmp_path / "recipe.db")
    accounts = tmp_path / "accounts.txt"
    accounts.write_text("alice alice-secret-passphrase\n")
    assert _run(["--accounts", str(accounts), "--database-url", url]).returncode == 0

    accounts.write_text("alice alice-secret-passphrase\nbob bob-secret-passphrase\n")
    result = _run(["--accounts", str(accounts), "--database-url", url])

    assert result.returncode == 0, result.stderr
    assert "provisioned: bob" in result.stdout
    assert "already existed (skipped): alice" in result.stdout
    assert _usernames(url) == ["alice", "bob"]


def test_cli_refuses_a_database_without_schema(tmp_path: Path) -> None:
    accounts = tmp_path / "accounts.txt"
    accounts.write_text("alice alice-secret-passphrase\n")

    result = _run(
        ["--accounts", str(accounts), "--database-url", f"sqlite:///{tmp_path / 'empty.db'}"]
    )

    assert result.returncode == 1
    assert "no schema" in result.stderr
