"""Operator CLI: recover one forgotten household password (root README.md
"Household password recovery").

    uv run python scripts/recover.py \
      --username alice \
      --password-file /path/outside/the/checkout/new-password.txt

Run it with the deployment stopped. The replacement password is read from a
file (or stdin with `-`), never the command line, so it never lands in shell
history, `ps` output, or a log. `--database-url` defaults to the configured
`RECIPE_DATABASE_URL` and is echoed so you can see which database is written.

On success: replaces the account's password hash, revokes all of its sessions,
prints the username and the revoked-session count (never the password), and
exits 0. On an unknown account, an invalid password, or a database with no
schema: prints the reason to stderr, changes nothing, and exits 1.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config import settings
from app.recover import RecoverError, recover_password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--username",
        required=True,
        help="The household account whose password is being recovered.",
    )
    parser.add_argument(
        "--password-file",
        required=True,
        help="File holding the replacement password, or '-' for stdin. Keep it "
        "outside the checkout, readable only by the operator, and delete it "
        "afterward.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Target database (default: RECIPE_DATABASE_URL).",
    )
    args = parser.parse_args(argv)

    database_url = args.database_url or settings.database_url

    try:
        raw = (
            sys.stdin.read()
            if args.password_file == "-"
            else Path(args.password_file).read_text()
        )
    except OSError as exc:
        print(f"recover failed: cannot read password file: {exc}", file=sys.stderr)
        return 1

    password = raw.strip()
    if not password:
        print("recover failed: password file is empty", file=sys.stderr)
        return 1

    try:
        result = recover_password(database_url, args.username, password)
    except RecoverError as exc:
        print(f"recover failed: {exc}", file=sys.stderr)
        return 1

    print(f"database: {database_url}")
    print(
        f"recovered: {result.username} "
        f"({result.sessions_revoked} session(s) revoked)"
    )
    print(
        "the old password and every previous session for this account no longer "
        "work — the member signs in with the new password."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
