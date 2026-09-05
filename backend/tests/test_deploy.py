"""Shell-level checks for the household deployment scripts under `deploy/`
(private-household-deployment ticket 04a).

The browser-observable "sign in and read/write the adopted data" path is the
`deployment` Playwright project (`frontend/e2e/smoke.deployment.spec.ts`). These
tests cover what is awkward to drive through a browser: that `deploy/install.sh`
carries existing data in via a snapshot and never overwrites an existing
deployment database, and that `deploy/control.sh` start/stop/status use one
explicit absolute database no matter the working directory.

The scripts are invoked exactly as an operator runs them — as subprocesses,
with `--skip-build` so no frontend build is needed (a stub `dist/` stands in
for the built assets `main.py` requires).
"""

from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app import models  # noqa: F401  — registers every table on Base.metadata
from app.database import Base
from sqlalchemy import create_engine, insert

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL = REPO_ROOT / "deploy" / "install.sh"
CONTROL = REPO_ROOT / "deploy" / "control.sh"
PORT = "8988"


def _seed_db(path: Path, titles: list[str]) -> None:
    """Create a real app-schema SQLite database at `path` with one recipe row
    per title."""
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        for title in titles:
            conn.execute(
                insert(models.Recipe).values(
                    title=title, notes="", tags=[], steps=[], created_at=now, updated_at=now
                )
            )
    engine.dispose()


def _recipe_titles(path: Path) -> list[str]:
    conn = sqlite3.connect(path)
    try:
        return sorted(row[0] for row in conn.execute("SELECT title FROM recipes"))
    finally:
        conn.close()


def _stub_dist(root: Path, name: str = "dist", marker: str | None = None) -> Path:
    """A stub built-frontend tree. With `marker`, drops a uniquely identifiable
    asset so a test can tell which build a running deployment is serving."""
    dist = root / name
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<!doctype html><div id="root"></div>')
    if marker is not None:
        (dist / "assets" / "build-marker.txt").write_text(marker)
    return dist


@pytest.fixture
def deploy_env(tmp_path: Path):
    """A disposable deployment layout: data/backup/runtime dirs and a stub build
    under `tmp_path`, the real repo as the checkout. Yields the env dict; always
    stops any server the test started."""
    data_dir = tmp_path / "data"
    env = {
        **os.environ,
        "RECIPE_DEPLOY_CHECKOUT": str(REPO_ROOT),
        "RECIPE_DEPLOY_DATA_DIR": str(data_dir),
        "RECIPE_DEPLOY_FRONTEND_DIST": str(_stub_dist(tmp_path)),
        "RECIPE_DEPLOY_PORT": PORT,
        "RECIPE_DEPLOY_ENV_FILE": str(tmp_path / "nonexistent.env"),
    }
    yield env
    subprocess.run(["bash", str(CONTROL), "stop"], env=env, capture_output=True, text=True)


def _run(script: Path, *args: str, env: dict, cwd: Path | str | None = None):
    return subprocess.run(
        ["bash", str(script), *args],
        env=env,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=90,
    )


def _wait_health(timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.3)
    return False


def test_install_adopts_existing_database_via_snapshot(deploy_env, tmp_path: Path):
    dev_db = tmp_path / "dev.db"
    _seed_db(dev_db, ["CARRIED OVER"])

    result = _run(INSTALL, "--skip-build", "--adopt-from", str(dev_db), env=deploy_env)
    assert result.returncode == 0, result.stderr

    deployment_db = tmp_path / "data" / "recipe.db"
    assert deployment_db.is_file()
    assert _recipe_titles(deployment_db) == ["CARRIED OVER"]
    # The adoption ran through the snapshot facility, leaving a recovery point.
    snapshots = list((tmp_path / "data" / "backups").glob("recipe-*.db"))
    assert len(snapshots) == 1


def test_install_never_overwrites_an_existing_deployment_database(deploy_env, tmp_path: Path):
    deployment_db = tmp_path / "data" / "recipe.db"
    deployment_db.parent.mkdir(parents=True)
    _seed_db(deployment_db, ["ALREADY LIVE"])

    other = tmp_path / "other.db"
    _seed_db(other, ["SHOULD NOT APPEAR"])

    result = _run(INSTALL, "--skip-build", "--adopt-from", str(other), env=deploy_env)
    assert result.returncode == 0, result.stderr
    assert "never overwrites an existing deployment database" in result.stdout
    assert _recipe_titles(deployment_db) == ["ALREADY LIVE"]


def test_install_without_a_source_defers_database_creation(deploy_env, tmp_path: Path):
    missing = tmp_path / "no-such.db"

    result = _run(INSTALL, "--skip-build", "--adopt-from", str(missing), env=deploy_env)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "data" / "recipe.db").exists()
    assert "fresh empty database will be created" in result.stdout


def test_a_database_inside_the_checkout_is_refused_by_every_entrypoint(deploy_env):
    # The guard lives in lib.sh, so it fires on `install.sh`, `control.sh start`,
    # `status`, ... — not just the one script.
    env = {**deploy_env, "RECIPE_DEPLOY_DB_FILE": str(REPO_ROOT / "backend" / "deploy-test.db")}
    for script, *args in ((INSTALL, "--skip-build"), (CONTROL, "start"), (CONTROL, "status")):
        result = _run(script, *args, env=env)
        assert result.returncode != 0
        assert "inside the checkout" in result.stderr


def test_control_lifecycle_uses_one_explicit_db_from_any_cwd(deploy_env, tmp_path: Path):
    dev_db = tmp_path / "dev.db"
    _seed_db(dev_db, ["PERSISTED RECORD"])
    assert _run(INSTALL, "--skip-build", "--adopt-from", str(dev_db), env=deploy_env).returncode == 0

    deployment_db = tmp_path / "data" / "recipe.db"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    # Start from a directory unrelated to the checkout and the data dir.
    started = _run(CONTROL, "start", env=deploy_env, cwd=elsewhere)
    assert started.returncode == 0, started.stderr + started.stdout
    assert _wait_health()

    # The explicit absolute path is the only database touched — no stray
    # recipe.db next to the caller or in the backend package.
    assert not (elsewhere / "recipe.db").exists()
    assert not (REPO_ROOT / "backend" / "recipe.db").exists()
    assert deployment_db.is_file()

    status = _run(CONTROL, "status", env=deploy_env, cwd=tmp_path)
    assert status.returncode == 0
    assert re.search(r"state\s*:\s*running \(pid \d+\)", status.stdout)
    assert str(deployment_db) in status.stdout
    assert re.search(r"database file\s*:\s*present", status.stdout)

    # A second start refuses rather than launching a duplicate.
    dup = _run(CONTROL, "start", env=deploy_env, cwd=elsewhere)
    assert dup.returncode != 0
    assert "already running" in dup.stderr

    assert _run(CONTROL, "stop", env=deploy_env).returncode == 0

    # Restart against the same database from yet another directory; the adopted
    # record is still there.
    restarted = _run(CONTROL, "start", env=deploy_env, cwd=REPO_ROOT)
    assert restarted.returncode == 0, restarted.stderr + restarted.stdout
    assert _wait_health()
    assert _recipe_titles(deployment_db) == ["PERSISTED RECORD"]

    assert _run(CONTROL, "stop", env=deploy_env).returncode == 0
    stopped = _run(CONTROL, "status", env=deploy_env)
    assert stopped.returncode == 3
    assert re.search(r"state\s*:\s*stopped", stopped.stdout)


# --- deploy/update.sh (private-household-deployment ticket 04b) -------------

UPDATE = REPO_ROOT / "deploy" / "update.sh"


def _snapshot_count(tmp_path: Path) -> int:
    return len(list((tmp_path / "data" / "backups").glob("recipe-*.db")))


def test_update_switches_build_snapshots_first_and_preserves_data(deploy_env, tmp_path: Path):
    dev_db = tmp_path / "dev.db"
    _seed_db(dev_db, ["SURVIVES THE UPDATE"])
    assert _run(INSTALL, "--skip-build", "--adopt-from", str(dev_db), env=deploy_env).returncode == 0

    deployment_db = tmp_path / "data" / "recipe.db"
    assert _run(CONTROL, "start", env=deploy_env).returncode == 0
    assert _wait_health()
    assert _snapshot_count(tmp_path) == 1  # the adoption snapshot

    next_build = _stub_dist(tmp_path, "next-dist", marker="NEW-BUILD-04b")
    result = _run(UPDATE, "--staging-dir", str(next_build), env=deploy_env)
    assert result.returncode == 0, result.stderr + result.stdout

    # A pre-maintenance snapshot was taken before the switch.
    assert _snapshot_count(tmp_path) == 2

    # The new build is now the served one; the staging and rollback dirs are
    # cleaned up on success (retaining an old build for on-demand return is 04c).
    live_dist = Path(deploy_env["RECIPE_DEPLOY_FRONTEND_DIST"])
    assert (live_dist / "assets" / "build-marker.txt").read_text() == "NEW-BUILD-04b"
    assert not (Path(str(live_dist) + ".prev")).exists()
    assert not (Path(str(live_dist) + ".staging")).exists()

    # Same explicit database, adopted record intact — no reset, no schema step.
    assert _wait_health()
    assert _recipe_titles(deployment_db) == ["SURVIVES THE UPDATE"]

    assert _run(CONTROL, "stop", env=deploy_env).returncode == 0


def test_update_aborts_on_bad_build_and_leaves_running_deployment_intact(deploy_env, tmp_path: Path):
    dev_db = tmp_path / "dev.db"
    _seed_db(dev_db, ["UNTOUCHED BY FAILED UPDATE"])
    assert _run(INSTALL, "--skip-build", "--adopt-from", str(dev_db), env=deploy_env).returncode == 0

    deployment_db = tmp_path / "data" / "recipe.db"
    assert _run(CONTROL, "start", env=deploy_env).returncode == 0
    assert _wait_health()

    live_dist = Path(deploy_env["RECIPE_DEPLOY_FRONTEND_DIST"])
    marker_before = (live_dist / "index.html").read_text()

    # A staging dir with no index.html: preparation must fail before anything is
    # switched, stopped, or snapshotted.
    broken = tmp_path / "broken-build"
    broken.mkdir()
    (broken / "assets").mkdir()
    result = _run(UPDATE, "--staging-dir", str(broken), env=deploy_env)
    assert result.returncode != 0
    assert "left intact" in result.stderr

    assert _snapshot_count(tmp_path) == 1  # no pre-maintenance snapshot taken
    assert not (Path(str(live_dist) + ".prev")).exists()
    assert (live_dist / "index.html").read_text() == marker_before
    assert _wait_health()  # old deployment still serving
    assert _recipe_titles(deployment_db) == ["UNTOUCHED BY FAILED UPDATE"]

    assert _run(CONTROL, "stop", env=deploy_env).returncode == 0
