"""Backup freshness reporting and local retention for the household deployment
(private-household-deployment ticket 07b).

Consumes only what `deploy/backup-run.sh` already leaves behind:

  * the snapshot directory — ``recipe-<UTC>.db`` files written by
    ``app.backup.create_backup``
  * ``backup-runs.log`` — one ``<UTC ISO8601> ok|FAIL <detail>`` line per
    scheduled run

and answers the two operator questions the spec's 24-hour recovery target
needs (spec items 12, 13, 32, 33):

  * :func:`gather` — is there a recent enough successful backup, and what was
    the last failed attempt? A stale or absent success is flagged; the CLI
    turns that into a non-zero exit so a plain wrapper notices without a
    hosted alerting service.
  * :func:`prune` — drop snapshots beyond the newest ``keep`` and nothing
    else. Count-based on purpose: a failed run publishes no snapshot, so it
    can never push an earlier success out of the retained set.

Incomplete files — a hidden ``.recipe-*.db.tmp`` from an interrupted copy, or
a ``recipe-*.db`` that will not open as an intact SQLite database — are
reported but never counted as a successful backup and never pruned.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import pathname2url

DEFAULT_KEEP = 14
DEFAULT_MAX_AGE = timedelta(hours=24)

_SNAPSHOT_RE = re.compile(r"^recipe-(\d{8}T\d{6}Z)\.db$")
_SNAPSHOT_TS_FORMAT = "%Y%m%dT%H%M%SZ"
_LOG_TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_LOG_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)\s+(?P<result>ok|FAIL)\s+(?P<detail>.*)$"
)


class BackupStatusError(Exception):
    """The report/prune inputs could not be read."""


def format_age(td: timedelta) -> str:
    """A short human age: hours below two days, days above."""
    hours = td.total_seconds() / 3600
    if hours < 48:
        return f"{hours:.1f}h"
    return f"{hours / 24:.1f}d"


@dataclass(frozen=True)
class Snapshot:
    path: Path
    taken_at: datetime  # UTC, parsed from the filename timestamp

    @property
    def name(self) -> str:
        return self.path.name


@dataclass(frozen=True)
class FailedRun:
    at: datetime  # UTC, from the run log line
    reason: str


@dataclass(frozen=True)
class BackupReport:
    now: datetime
    keep: int
    max_age: timedelta
    valid: list[Snapshot]  # newest first
    incomplete: list[Path]  # hidden ``.tmp`` partials — sorted by name
    unreadable: list[Path]  # ``recipe-*.db`` that would not open as SQLite
    latest_failure: FailedRun | None

    @property
    def latest_success(self) -> Snapshot | None:
        return self.valid[0] if self.valid else None

    @property
    def age(self) -> timedelta | None:
        latest = self.latest_success
        return None if latest is None else self.now - latest.taken_at

    @property
    def fresh(self) -> bool:
        age = self.age
        return age is not None and age <= self.max_age

    @property
    def problem(self) -> str | None:
        """One line naming why the backup position misses the recovery target,
        or ``None`` when a recent successful snapshot is on disk."""
        if self.latest_success is None:
            return "no successful backup on local disk"
        if not self.fresh:
            return (
                f"latest backup is {format_age(self.age)} old — older than the "
                f"{format_age(self.max_age)} recovery target"
            )
        return None

    @property
    def surplus(self) -> list[Snapshot]:
        """Valid snapshots beyond the newest ``keep`` — the prune candidates."""
        return self.valid[self.keep :]


@dataclass(frozen=True)
class PruneOutcome:
    report: BackupReport
    removed: list[Path]
    kept: list[Snapshot]  # newest first — the retained set
    failed: list[tuple[Path, str]]  # (path, error) for delete attempts that raised

    @property
    def ok(self) -> bool:
        return not self.failed


def gather(
    dest_dir: Path | str,
    *,
    log_path: Path | str | None = None,
    now: datetime | None = None,
    keep: int = DEFAULT_KEEP,
    max_age: timedelta = DEFAULT_MAX_AGE,
) -> BackupReport:
    """Read the snapshot directory and (optionally) the run log into a
    :class:`BackupReport`. Raises :class:`BackupStatusError` if ``keep`` is
    below 1 or ``dest_dir`` is not a directory."""
    if keep < 1:
        raise BackupStatusError(f"keep must be >= 1, got {keep}")

    dest_dir = Path(dest_dir)
    if not dest_dir.is_dir():
        raise BackupStatusError(f"backup directory does not exist: {dest_dir}")

    now = _as_utc(now) if now is not None else datetime.now(timezone.utc)

    valid: list[Snapshot] = []
    incomplete: list[Path] = []
    unreadable: list[Path] = []

    for entry in dest_dir.iterdir():
        if not entry.is_file():
            continue
        name = entry.name
        if name.startswith(".") and name.endswith(".tmp"):
            incomplete.append(entry)
            continue
        match = _SNAPSHOT_RE.match(name)
        if match is None:
            continue  # an unrelated file — never counted, never pruned
        taken_at = datetime.strptime(match.group(1), _SNAPSHOT_TS_FORMAT).replace(
            tzinfo=timezone.utc
        )
        if _looks_like_backup(entry):
            valid.append(Snapshot(path=entry, taken_at=taken_at))
        else:
            unreadable.append(entry)

    valid.sort(key=lambda s: (s.taken_at, s.name), reverse=True)

    return BackupReport(
        now=now,
        keep=keep,
        max_age=max_age,
        valid=valid,
        incomplete=sorted(incomplete),
        unreadable=sorted(unreadable),
        latest_failure=_latest_failure(log_path),
    )


def prune(
    dest_dir: Path | str,
    *,
    keep: int = DEFAULT_KEEP,
    log_path: Path | str | None = None,
    now: datetime | None = None,
    max_age: timedelta = DEFAULT_MAX_AGE,
    dry_run: bool = False,
) -> PruneOutcome:
    """Delete valid snapshots beyond the newest ``keep``. Only ever removes
    ``recipe-<UTC>.db`` files that opened as an intact backup — never a
    partial, an unreadable file, an unrelated file, or the run log. A delete
    that raises is captured in ``failed`` and leaves the retained set intact."""
    report = gather(dest_dir, log_path=log_path, now=now, keep=keep, max_age=max_age)

    removed: list[Path] = []
    failed: list[tuple[Path, str]] = []
    for snap in report.surplus:
        if dry_run:
            continue
        try:
            snap.path.unlink()
        except OSError as exc:
            failed.append((snap.path, str(exc)))
        else:
            removed.append(snap.path)

    removed_set = set(removed)
    kept = [s for s in report.valid if s.path not in removed_set]
    return PruneOutcome(report=report, removed=removed, kept=kept, failed=failed)


def _as_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _looks_like_backup(path: Path) -> bool:
    """True only if ``path`` opens read-only as an intact SQLite database that
    carries this app's ``recipes`` table. A torn or truncated copy fails here,
    so an incomplete file is never reported as a successful backup.

    Deliberately lighter than ``app.restore._validate_snapshot`` (which gates a
    live-database overwrite and checks the full schema): this only classifies a
    file for a freshness report, so a cheap "is it a real recipe-app snapshot"
    check is enough and keeps this module free of the ORM.
    """
    uri = f"file:{pathname2url(str(path))}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=5)
    except sqlite3.Error:
        return False
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        tables = {name for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    except sqlite3.Error:
        return False
    finally:
        conn.close()
    return bool(row) and row[0] == "ok" and "recipes" in tables


def _latest_failure(log_path: Path | str | None) -> FailedRun | None:
    if log_path is None:
        return None
    log_path = Path(log_path)
    if not log_path.is_file():
        return None
    latest: FailedRun | None = None
    for raw in log_path.read_text().splitlines():
        match = _LOG_LINE_RE.match(raw.strip())
        if match is None or match.group("result") != "FAIL":
            continue
        at = datetime.strptime(match.group("ts"), _LOG_TS_FORMAT).replace(tzinfo=timezone.utc)
        if latest is None or at >= latest.at:
            latest = FailedRun(at=at, reason=match.group("detail"))
    return latest
