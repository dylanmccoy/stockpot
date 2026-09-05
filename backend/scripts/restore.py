"""Operator CLI: rehearse recovery of a snapshot into a separate database
(root README.md "Restore rehearsal").

    uv run python scripts/restore.py \
      --snapshot /path/outside/the/checkout/recipe-<UTC timestamp>.db \
      --target /tmp/recipe-rehearsal.db

Both paths are explicit. `--snapshot` is validated and only read. `--target`
must not already exist — this rehearses recovery in isolation and never
replaces a live database. Exits 0 and prints the recovered path on success;
exits 1 and prints the failure to stderr otherwise, creating no target
database and leaving the snapshot untouched.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.restore import RestoreError, recover_snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot",
        required=True,
        type=Path,
        help="Snapshot file to recover from (produced by scripts/backup.py).",
    )
    parser.add_argument(
        "--target",
        required=True,
        type=Path,
        help="New database path to create. Must not already exist.",
    )
    args = parser.parse_args(argv)

    try:
        recovered = recover_snapshot(args.snapshot, args.target)
    except RestoreError as exc:
        print(f"restore failed: {exc}", file=sys.stderr)
        return 1

    print(f"restore ok: {recovered}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
