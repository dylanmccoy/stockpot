"""Operator CLI: provision household login accounts (root README.md
"Household account provisioning").

    uv run python scripts/provision.py --accounts /path/outside/the/checkout/accounts.txt

Run it with the deployment stopped. Each non-blank, non-`#` line of the
accounts file is `<username> <password>` (split on the first run of
whitespace); the password is read from the file rather than the command line
so it never lands in shell history, `ps` output, or a log. `--database-url`
defaults to the configured `RECIPE_DATABASE_URL` and is echoed so you can see
which database is being written.

Registration is never opened: the script writes straight to the configured
database. A username that already exists is left alone and reported as
skipped, so adding a member later is a re-run with one more line.

Exits 0 on success (printing a created/skipped summary with usernames only,
never passwords); exits 1 and prints the reason to stderr — committing
nothing — on a malformed file, an invalid username/password, or a database
with no schema.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config import settings
from app.provision import ProvisionError, provision_accounts


def _parse_accounts(text: str) -> list[tuple[str, str]]:
    accounts: list[tuple[str, str]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2 or not parts[1].strip():
            raise ProvisionError(
                f"accounts file line {lineno}: expected '<username> <password>'"
            )
        accounts.append((parts[0], parts[1].strip()))
    if not accounts:
        raise ProvisionError("accounts file has no account lines")
    return accounts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--accounts",
        required=True,
        help="File of '<username> <password>' lines, or '-' for stdin. Keep it "
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
        text = sys.stdin.read() if args.accounts == "-" else Path(args.accounts).read_text()
    except OSError as exc:
        print(f"provision failed: cannot read accounts file: {exc}", file=sys.stderr)
        return 1

    try:
        accounts = _parse_accounts(text)
        result = provision_accounts(database_url, accounts)
    except ProvisionError as exc:
        print(f"provision failed: {exc}", file=sys.stderr)
        return 1

    print(f"database: {database_url}")
    if result.created:
        print(f"provisioned: {', '.join(result.created)}")
    if result.skipped:
        print(f"already existed (skipped): {', '.join(result.skipped)}")
    print(
        "registration stays closed — start the app without "
        "RECIPE_ALLOW_REGISTRATION and confirm POST /api/auth/register returns 403."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
