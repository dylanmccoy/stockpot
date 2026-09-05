"""Operator CLI: take a live SQLite snapshot (root README.md "Backup").

    uv run python scripts/backup.py --dest-dir /path/outside/the/checkout

Defaults `--source` to the configured `RECIPE_DATABASE_URL` (must be a
file-backed `sqlite:///` URL). Exits 0 and prints the snapshot path on
success; exits 1 and prints the failure to stderr otherwise, leaving any
earlier snapshots in `--dest-dir` untouched.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.backup import BackupError, create_backup
from app.config import settings


def _source_from_database_url(url: str) -> Path:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        raise BackupError(f"backup requires a file-backed sqlite:/// database_url, got: {url!r}")
    return Path(url[len(prefix) :])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest-dir",
        required=True,
        type=Path,
        help="Snapshot directory. Keep it outside the checkout and served frontend assets.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Source database file (default: RECIPE_DATABASE_URL).",
    )
    args = parser.parse_args(argv)

    try:
        source = args.source or _source_from_database_url(settings.database_url)
        snapshot = create_backup(source, args.dest_dir)
    except BackupError as exc:
        print(f"backup failed: {exc}", file=sys.stderr)
        return 1

    print(f"backup ok: {snapshot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
