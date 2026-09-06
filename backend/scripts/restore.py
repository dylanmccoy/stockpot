"""Operator CLI: recover a snapshot — into a separate rehearsal database, or
in place over the live one with writers stopped (root README.md "Restore
rehearsal" / "Restore in place").

    # rehearsal (default): --target must NOT exist
    uv run python scripts/restore.py \
      --snapshot /path/outside/the/checkout/recipe-<UTC timestamp>.db \
      --target /tmp/recipe-rehearsal.db

    # replace the live database in place: --target MUST exist, writers stopped
    uv run python scripts/restore.py --replace \
      --snapshot /path/outside/the/checkout/recipe-<UTC timestamp>.db \
      --target "$RECIPE_DEPLOY_DATA_DIR/recipe.db" \
      --preserve-dir /path/outside/the/checkout/pre-restore

`--snapshot` is validated and only read. Without `--replace` this rehearses
recovery in isolation and refuses an existing `--target`. With `--replace` it
snapshots the current `--target` into `--preserve-dir` first and refuses to go
further if that preservation or its validation fails, so the replaced database
is never lost.

Exits 0 on success (printing the recovered path, and with `--replace` the
preserved copy); exits 1 and prints the failure to stderr otherwise, leaving
the target and every earlier snapshot untouched.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.restore import RestoreError, recover_snapshot, replace_database


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
        help="Database path. Must NOT exist by default; MUST exist with --replace.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace an existing --target in place, writers stopped. Requires "
        "--preserve-dir.",
    )
    parser.add_argument(
        "--preserve-dir",
        type=Path,
        default=None,
        help="With --replace: directory to snapshot the current --target into "
        "before it is replaced. Keep it outside the checkout, operator-only.",
    )
    args = parser.parse_args(argv)

    if args.replace and args.preserve_dir is None:
        parser.error("--replace requires --preserve-dir")
    if args.preserve_dir is not None and not args.replace:
        parser.error("--preserve-dir is only meaningful with --replace")

    try:
        if args.replace:
            result = replace_database(
                args.snapshot, args.target, preserve_dir=args.preserve_dir
            )
            print(f"restore ok: replaced {result.target}")
            print(f"preserved prior database: {result.preserved}")
        else:
            recovered = recover_snapshot(args.snapshot, args.target)
            print(f"restore ok: {recovered}")
    except RestoreError as exc:
        print(f"restore failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
