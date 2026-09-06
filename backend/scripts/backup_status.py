"""Operator CLI: report local backup freshness and apply local retention
(root README.md "Operating the server" runbook 14; private-household-deployment
ticket 07b).

    # freshness report — exit 0 fresh, 1 stale / none on disk, 2 bad input
    uv run python scripts/backup_status.py \
      --dest-dir /path/outside/the/checkout \
      --log "$RECIPE_DEPLOY_RUNTIME_DIR/backup-runs.log"

    # apply retention: keep the newest N valid snapshots, drop older ones
    uv run python scripts/backup_status.py \
      --dest-dir /path/outside/the/checkout --keep 14 --prune

The report reads only the snapshot directory and the run log. `--prune` only
ever deletes ``recipe-<UTC>.db`` files beyond the newest ``--keep`` that open
as an intact backup — never a partial, an unrelated file, or the log — and a
failed run never makes an earlier success eligible. `--now` (UTC ISO8601)
overrides the current time for what-if checks and tests.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.backup_status import (
    DEFAULT_KEEP,
    DEFAULT_MAX_AGE,
    BackupReport,
    BackupStatusError,
    PruneOutcome,
    format_age,
    gather,
    prune,
)


def _parse_now(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest-dir",
        required=True,
        type=Path,
        help="Snapshot directory (RECIPE_DEPLOY_BACKUP_DIR).",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help="backup-runs.log, for the latest failed attempt.",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=DEFAULT_KEEP,
        help=f"Valid snapshots to retain, newest first (default {DEFAULT_KEEP}).",
    )
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=DEFAULT_MAX_AGE.total_seconds() / 3600,
        help="Flag the latest success older than this many hours (default 24).",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Delete valid snapshots beyond --keep.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With --prune: report what would be deleted, delete nothing.",
    )
    parser.add_argument(
        "--now",
        type=_parse_now,
        default=None,
        help="Override the current UTC time (ISO8601) for age checks / tests.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Print only problems — for unattended callers.",
    )
    args = parser.parse_args(argv)

    max_age = timedelta(hours=args.max_age_hours)

    try:
        if args.prune:
            outcome: PruneOutcome | None = prune(
                args.dest_dir,
                keep=args.keep,
                log_path=args.log,
                now=args.now,
                max_age=max_age,
                dry_run=args.dry_run,
            )
            report = outcome.report
        else:
            outcome = None
            report = gather(
                args.dest_dir,
                log_path=args.log,
                now=args.now,
                keep=args.keep,
                max_age=max_age,
            )
    except BackupStatusError as exc:
        print(f"backup-status failed: {exc}", file=sys.stderr)
        return 2

    _print_report(report, quiet=args.quiet)
    if outcome is not None:
        _print_prune(outcome, dry_run=args.dry_run, quiet=args.quiet)

    if outcome is not None and not outcome.ok:
        return 2
    return 0 if report.problem is None else 1


def _print_report(report: BackupReport, *, quiet: bool) -> None:
    if not quiet:
        if report.latest_success is not None:
            print(f"latest success  : {report.latest_success.name}  ({format_age(report.age)} old)")
            print(f"                  {report.latest_success.path}")
        else:
            print("latest success  : NONE on local disk")

        if report.latest_failure is not None:
            stamp = report.latest_failure.at.strftime("%Y-%m-%dT%H:%M:%SZ")
            print(f"latest failure  : {stamp}  {report.latest_failure.reason}")
        else:
            print("latest failure  : none recorded")

        print(f"valid snapshots : {len(report.valid)}  (retention keeps newest {report.keep})")
        if report.incomplete:
            names = ", ".join(p.name for p in report.incomplete)
            print(f"incomplete      : {len(report.incomplete)} not counted — {names}")
        if report.unreadable:
            names = ", ".join(p.name for p in report.unreadable)
            print(f"unreadable      : {len(report.unreadable)} not counted — {names}")

    problem = report.problem
    if problem is None:
        if not quiet:
            print(f"status          : OK — within the {format_age(report.max_age)} recovery target")
    else:
        print(f"status          : STALE — {problem}", file=sys.stderr)


def _print_prune(outcome: PruneOutcome, *, dry_run: bool, quiet: bool) -> None:
    if dry_run:
        for snap in outcome.report.surplus:
            print(f"would remove    : {snap.name}")
        if not outcome.report.surplus and not quiet:
            print("retention       : nothing to prune")
    else:
        for path in outcome.removed:
            print(f"removed         : {path.name}")
        if not outcome.removed and not outcome.failed and not quiet:
            print("retention       : nothing to prune")

    for path, err in outcome.failed:
        print(f"prune FAILED    : {path.name}: {err}", file=sys.stderr)

    if not quiet and not dry_run:
        print(f"retained        : {len(outcome.kept)} newest valid snapshot(s)")


if __name__ == "__main__":
    raise SystemExit(main())
