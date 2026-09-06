"""Backup freshness reporting and local retention (private-household-deployment
ticket 07b).

`app.backup_status` and its operator CLI `scripts/backup_status.py` are driven
against disposable snapshot directories with an injected "now", so the 24-hour
recovery target and the count-based retention are exercised deterministically
without waiting on a real schedule.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import models  # noqa: F401  — populates Base.metadata with every table
from app.backup_status import (
    BackupStatusError,
    gather,
    prune,
)
from app.database import Base, make_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent
CLI = BACKEND_DIR / "scripts" / "backup_status.py"

NOW = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


def _snapshot(dest_dir: Path, taken_at: datetime) -> Path:
    """Write a real app-schema SQLite file named like a real snapshot."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"recipe-{taken_at.strftime('%Y%m%dT%H%M%SZ')}.db"
    engine = make_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    return path


def _log(dir_: Path, *lines: str) -> Path:
    path = dir_ / "backup-runs.log"
    path.write_text("".join(line + "\n" for line in lines))
    return path


def _hours_before(hours: float) -> datetime:
    return NOW - timedelta(hours=hours)


# --- freshness report (acceptance criterion 1) -----------------------------


def test_report_exposes_latest_success_its_age_and_the_latest_failure(tmp_path: Path):
    backups = tmp_path / "backups"
    _snapshot(backups, _hours_before(50))
    newest = _snapshot(backups, _hours_before(2))
    log = _log(
        tmp_path,
        "2026-09-03T03:30:00Z ok /b/recipe-20260903T033000Z.db",
        "2026-09-04T03:30:00Z FAIL destination /b unwritable: [Errno 13] Permission denied",
        "2026-09-05T03:30:00Z ok /b/recipe-20260905T100000Z.db",
    )

    report = gather(backups, log_path=log, now=NOW, keep=14)

    assert report.latest_success is not None
    assert report.latest_success.path == newest
    assert report.age == timedelta(hours=2)
    assert report.fresh is True
    assert report.problem is None
    assert report.latest_failure is not None
    assert report.latest_failure.at == datetime(2026, 9, 4, 3, 30, tzinfo=timezone.utc)
    assert "Permission denied" in report.latest_failure.reason


def test_flags_no_successful_backup_on_disk(tmp_path: Path):
    backups = tmp_path / "backups"
    backups.mkdir()

    report = gather(backups, now=NOW)

    assert report.latest_success is None
    assert report.age is None
    assert report.problem == "no successful backup on local disk"


def test_flags_a_success_older_than_the_recovery_target(tmp_path: Path):
    backups = tmp_path / "backups"
    _snapshot(backups, _hours_before(30))

    report = gather(backups, now=NOW, max_age=timedelta(hours=24))

    assert report.fresh is False
    assert report.problem is not None
    assert "older than the" in report.problem


def test_a_recent_success_is_not_flagged(tmp_path: Path):
    backups = tmp_path / "backups"
    _snapshot(backups, _hours_before(23))

    assert gather(backups, now=NOW, max_age=timedelta(hours=24)).problem is None


# --- incomplete / unreadable files (acceptance criterion 3) ----------------


def test_incomplete_and_unreadable_files_are_never_counted_as_a_success(tmp_path: Path):
    backups = tmp_path / "backups"
    good = _snapshot(backups, _hours_before(2))
    (backups / ".recipe-20260905T110000Z.db.tmp").write_bytes(b"half a copy")
    torn = backups / "recipe-20260905T113000Z.db"
    torn.write_bytes(b"SQLite format 3\x00 then nonsense")

    report = gather(backups, now=NOW)

    assert [s.path for s in report.valid] == [good]
    assert report.latest_success.path == good
    assert backups / ".recipe-20260905T110000Z.db.tmp" in report.incomplete
    assert torn in report.unreadable


def test_a_directory_with_only_an_incomplete_file_has_no_successful_backup(tmp_path: Path):
    backups = tmp_path / "backups"
    backups.mkdir()
    (backups / ".recipe-20260905T110000Z.db.tmp").write_bytes(b"half a copy")

    report = gather(backups, now=NOW)

    assert report.valid == []
    assert report.problem == "no successful backup on local disk"


def test_a_missing_backup_directory_is_an_input_error(tmp_path: Path):
    with pytest.raises(BackupStatusError, match="does not exist"):
        gather(tmp_path / "nope", now=NOW)


def test_keep_below_one_is_rejected(tmp_path: Path):
    (tmp_path / "backups").mkdir()
    with pytest.raises(BackupStatusError, match="keep must be >= 1"):
        gather(tmp_path / "backups", now=NOW, keep=0)


# --- retention (acceptance criteria 2 and 4) -------------------------------


def test_prune_keeps_the_newest_keep_valid_snapshots_and_drops_the_rest(tmp_path: Path):
    backups = tmp_path / "backups"
    made = [_snapshot(backups, _hours_before(h)) for h in (120, 96, 72, 48, 24, 2)]
    oldest_four, newest_two = made[:4], made[4:]

    outcome = prune(backups, keep=2, now=NOW)

    assert sorted(outcome.removed) == sorted(oldest_four)
    assert [s.path for s in outcome.kept] == list(reversed(newest_two))
    assert {p.name for p in backups.glob("recipe-*.db")} == {p.name for p in newest_two}
    assert outcome.ok


def test_a_failed_run_never_evicts_an_earlier_success(tmp_path: Path):
    # Two good recovery points and a run log that ends in failures. Retention
    # is count-based, so nothing is eligible to drop — the failed runs added no
    # snapshot. The earlier successes stay put.
    backups = tmp_path / "backups"
    older = _snapshot(backups, _hours_before(50))
    newer = _snapshot(backups, _hours_before(26))
    log = _log(
        tmp_path,
        "2026-09-03T03:30:00Z ok /b/recipe-20260903T100000Z.db",
        "2026-09-04T03:30:00Z ok /b/recipe-20260904T100000Z.db",
        "2026-09-05T03:30:00Z FAIL deployment database ... does not exist ...",
    )

    outcome = prune(backups, keep=3, log_path=log, now=NOW)

    assert outcome.removed == []
    assert {p.name for p in backups.glob("recipe-*.db")} == {older.name, newer.name}
    assert outcome.report.latest_success.path == newer
    assert outcome.report.latest_failure is not None
    assert outcome.report.latest_failure.reason.startswith("deployment database")


def test_prune_never_touches_partials_or_unrelated_files(tmp_path: Path):
    backups = tmp_path / "backups"
    for h in (72, 48, 24, 2):
        _snapshot(backups, _hours_before(h))
    partial = backups / ".recipe-20260905T113000Z.db.tmp"
    partial.write_bytes(b"in flight")
    keep_me = backups / "README.txt"
    keep_me.write_text("operator notes")

    prune(backups, keep=1, now=NOW)

    assert partial.is_file()
    assert keep_me.is_file()
    assert len(list(backups.glob("recipe-*.db"))) == 1


def test_dry_run_reports_the_surplus_without_deleting_anything(tmp_path: Path):
    backups = tmp_path / "backups"
    made = [_snapshot(backups, _hours_before(h)) for h in (72, 48, 24, 2)]

    outcome = prune(backups, keep=1, now=NOW, dry_run=True)

    assert outcome.removed == []
    assert [s.path for s in outcome.report.surplus] == list(reversed(made[:3]))
    assert len(list(backups.glob("recipe-*.db"))) == 4


def test_a_delete_that_fails_is_reported_and_leaves_the_retained_set_intact(tmp_path: Path):
    backups = tmp_path / "backups"
    made = [_snapshot(backups, _hours_before(h)) for h in (72, 48, 2)]
    os.chmod(backups, 0o500)  # entries cannot be unlinked
    try:
        outcome = prune(backups, keep=1, now=NOW)
    finally:
        os.chmod(backups, 0o700)

    assert outcome.ok is False
    assert {p for p, _ in outcome.failed} == set(made[:2])
    assert {p.name for p in backups.glob("recipe-*.db")} == {p.name for p in made}


# --- operator CLI (the real operator operation, acceptance criterion 4) ----


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=BACKEND_DIR,
        env={**os.environ},
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_cli_reports_a_fresh_backup_and_exits_zero(tmp_path: Path):
    backups = tmp_path / "backups"
    _snapshot(backups, _hours_before(3))
    log = _log(tmp_path, "2026-09-01T03:30:00Z FAIL something earlier")

    result = _run_cli(
        "--dest-dir", str(backups),
        "--log", str(log),
        "--now", NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    assert result.returncode == 0, result.stderr
    assert "latest success  :" in result.stdout
    assert "3.0h old" in result.stdout
    assert "latest failure  : 2026-09-01T03:30:00Z  something earlier" in result.stdout
    assert "status          : OK" in result.stdout


def test_cli_exits_one_when_the_latest_backup_is_stale(tmp_path: Path):
    backups = tmp_path / "backups"
    _snapshot(backups, _hours_before(40))

    result = _run_cli(
        "--dest-dir", str(backups),
        "--now", NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    assert result.returncode == 1
    assert "STALE" in result.stderr


def test_cli_exits_one_when_there_is_no_successful_backup(tmp_path: Path):
    backups = tmp_path / "backups"
    backups.mkdir()

    result = _run_cli("--dest-dir", str(backups), "--now", NOW.strftime("%Y-%m-%dT%H:%M:%SZ"))

    assert result.returncode == 1
    assert "no successful backup" in result.stderr


def test_cli_exits_two_on_a_missing_directory(tmp_path: Path):
    result = _run_cli("--dest-dir", str(tmp_path / "nope"))
    assert result.returncode == 2
    assert "backup-status failed" in result.stderr


def test_cli_prune_applies_retention_and_reports_what_it_removed(tmp_path: Path):
    backups = tmp_path / "backups"
    made = [_snapshot(backups, _hours_before(h)) for h in (72, 48, 24, 2)]

    result = _run_cli(
        "--dest-dir", str(backups),
        "--keep", "2",
        "--prune",
        "--now", NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    assert result.returncode == 0, result.stderr
    assert f"removed         : {made[0].name}" in result.stdout
    assert f"removed         : {made[1].name}" in result.stdout
    assert {p.name for p in backups.glob("recipe-*.db")} == {made[2].name, made[3].name}
