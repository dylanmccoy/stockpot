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

import contextlib
import json
import os
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import textwrap
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
SUPERVISE = REPO_ROOT / "deploy" / "supervise.sh"
KEEPER = REPO_ROOT / "deploy" / "wsl-keeper.sh"
PORT = "8988"


def _recipe_row(title: str) -> dict:
    """Column values for one `recipes` row with the given title."""
    now = datetime.now(timezone.utc)
    return {
        "title": title,
        "notes": "",
        "tags": [],
        "steps": [],
        "created_at": now,
        "updated_at": now,
    }


def _seed_db(path: Path, titles: list[str]) -> None:
    """Create a real app-schema SQLite database at `path` with one recipe row
    per title."""
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for title in titles:
            conn.execute(insert(models.Recipe).values(**_recipe_row(title)))
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
    # Tear down top-down: the keeper (which would relaunch the supervisor), then
    # the supervisor (which would restart the app), then the app. Each stop is a
    # no-op if the test never started that layer.
    subprocess.run(["bash", str(KEEPER), "stop"], env=env, capture_output=True, text=True)
    subprocess.run(["bash", str(SUPERVISE), "stop"], env=env, capture_output=True, text=True)
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


def _wait_health(timeout: float = 30.0, port: str = PORT) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/health", timeout=2
            ) as r:
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


# --- deploy/rollback.sh (private-household-deployment ticket 04c) -----------

ROLLBACK = REPO_ROOT / "deploy" / "rollback.sh"


def _retained_builds(tmp_path: Path) -> list[Path]:
    archive = tmp_path / "data" / "builds"
    return sorted(p for p in archive.iterdir() if p.is_dir()) if archive.is_dir() else []


def test_rollback_returns_to_the_retained_previous_build_and_preserves_data(
    deploy_env, tmp_path: Path
):
    dev_db = tmp_path / "dev.db"
    _seed_db(dev_db, ["KEPT ACROSS ROLLBACK"])
    assert _run(INSTALL, "--skip-build", "--adopt-from", str(dev_db), env=deploy_env).returncode == 0

    deployment_db = tmp_path / "data" / "recipe.db"
    live_dist = Path(deploy_env["RECIPE_DEPLOY_FRONTEND_DIST"])
    # Tag the installed build so the test can tell which build is being served.
    (live_dist / "assets" / "build-marker.txt").write_text("BUILD-1")

    assert _run(CONTROL, "start", env=deploy_env).returncode == 0
    assert _wait_health()
    assert _snapshot_count(tmp_path) == 1  # the adoption snapshot

    # Update to BUILD-2 — update.sh retains BUILD-1 in the build archive.
    next_build = _stub_dist(tmp_path, "next-dist", marker="BUILD-2")
    assert _run(UPDATE, "--staging-dir", str(next_build), env=deploy_env).returncode == 0
    assert (live_dist / "assets" / "build-marker.txt").read_text() == "BUILD-2"
    assert _snapshot_count(tmp_path) == 2
    retained = _retained_builds(tmp_path)
    assert len(retained) == 1
    assert (retained[0] / "assets" / "build-marker.txt").read_text() == "BUILD-1"

    # Deliberate operator rollback to the most recently retained build.
    result = _run(ROLLBACK, env=deploy_env)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "rollback complete" in result.stdout

    # A pre-maintenance snapshot was taken before the switch.
    assert _snapshot_count(tmp_path) == 3
    # BUILD-1 is the served build again; same explicit DB, adopted record intact.
    assert (live_dist / "assets" / "build-marker.txt").read_text() == "BUILD-1"
    assert not (Path(str(live_dist) + ".prev")).exists()
    assert not (Path(str(live_dist) + ".staging")).exists()
    assert _wait_health()
    assert _recipe_titles(deployment_db) == ["KEPT ACROSS ROLLBACK"]

    # rollback.sh does not archive; the update's retained BUILD-1 is unchanged
    # (moving forward again is a deploy/update.sh build, not a rollback).
    markers = sorted(
        p.read_text() for p in (tmp_path / "data" / "builds").glob("*/assets/build-marker.txt")
    )
    assert markers == ["BUILD-1"]

    assert _run(CONTROL, "stop", env=deploy_env).returncode == 0


def test_rollback_aborts_on_bad_selection_and_leaves_running_deployment_intact(
    deploy_env, tmp_path: Path
):
    dev_db = tmp_path / "dev.db"
    _seed_db(dev_db, ["UNTOUCHED BY FAILED ROLLBACK"])
    assert _run(INSTALL, "--skip-build", "--adopt-from", str(dev_db), env=deploy_env).returncode == 0

    deployment_db = tmp_path / "data" / "recipe.db"
    live_dist = Path(deploy_env["RECIPE_DEPLOY_FRONTEND_DIST"])
    (live_dist / "assets" / "build-marker.txt").write_text("RUNNING")
    assert _run(CONTROL, "start", env=deploy_env).returncode == 0
    assert _wait_health()

    # No retained build yet (no update has run): a no-arg rollback must refuse
    # without touching the running deployment.
    r1 = _run(ROLLBACK, env=deploy_env)
    assert r1.returncode != 0
    assert "no retained build" in r1.stderr

    # An explicit --to that resolves to nothing: same guarantee.
    r2 = _run(ROLLBACK, "--to", str(tmp_path / "no-such-build"), env=deploy_env)
    assert r2.returncode != 0
    assert "nothing switched" in r2.stderr

    # A --to directory that exists but is not a usable build: refused before any
    # switch, stop, or snapshot.
    unusable = tmp_path / "unusable-build"
    (unusable / "assets").mkdir(parents=True)
    r3 = _run(ROLLBACK, "--to", str(unusable), env=deploy_env)
    assert r3.returncode != 0
    assert "no index.html" in r3.stderr

    assert _snapshot_count(tmp_path) == 1  # no pre-maintenance snapshot taken
    assert not (Path(str(live_dist) + ".prev")).exists()
    assert (live_dist / "assets" / "build-marker.txt").read_text() == "RUNNING"
    assert _wait_health()  # deployment still serving on the same build
    assert _recipe_titles(deployment_db) == ["UNTOUCHED BY FAILED ROLLBACK"]

    assert _run(CONTROL, "stop", env=deploy_env).returncode == 0


def test_rollback_list_reports_retained_builds(deploy_env, tmp_path: Path):
    dev_db = tmp_path / "dev.db"
    _seed_db(dev_db, ["R"])
    assert _run(INSTALL, "--skip-build", "--adopt-from", str(dev_db), env=deploy_env).returncode == 0

    before_any = _run(ROLLBACK, "--list", env=deploy_env)
    assert before_any.returncode == 0
    assert "none" in before_any.stdout

    assert _run(CONTROL, "start", env=deploy_env).returncode == 0
    assert _wait_health()
    next_build = _stub_dist(tmp_path, "next-dist", marker="X")
    assert _run(UPDATE, "--staging-dir", str(next_build), env=deploy_env).returncode == 0

    listed = _run(ROLLBACK, "--list", env=deploy_env)
    assert listed.returncode == 0
    retained = _retained_builds(tmp_path)
    assert len(retained) == 1
    assert retained[0].name in listed.stdout

    assert _run(CONTROL, "stop", env=deploy_env).returncode == 0


# --- private HTTPS ingress (private-household-deployment ticket 05a) --------
#
# deploy/tailscale-serve.sh configures Windows Tailscale Serve to proxy the
# deployment's local origin over tailnet HTTPS; deploy/net-check.sh is the
# repeatable connectivity check. Real Tailscale needs a tailnet and Windows,
# so these drive both scripts against a STUB `tailscale` CLI (argv logged, a
# tiny state file for the serve mapping) — no credentials, fully deterministic,
# runs in the `backend` CI job. Real-host behaviour is the separate acceptance
# gate recorded in .scratch/private-household-deployment/host-acceptance-05a.md.

TAILSCALE_SERVE = REPO_ROOT / "deploy" / "tailscale-serve.sh"
NET_CHECK = REPO_ROOT / "deploy" / "net-check.sh"


@pytest.fixture
def ts_stub(tmp_path: Path):
    """A stub Tailscale CLI. Returns (env_patch, log_path, state_path); the
    caller merges env_patch into a deploy env. Behaviour knobs, via env:
      TS_STUB_FUNNEL=on      -> `funnel status` reports an active funnel
      TS_STUB_FUNNEL=err     -> `funnel status` exits non-zero (unknowable)
      TS_STUB_STOPPED=1      -> `status` reports Tailscale stopped
      TS_STUB_DNSNAME=<name> -> `status --json` .Self.DNSName
    `status --json` also emits a decoy .Peer with a different DNSName, so a
    test proves .Self is the one picked. `serve --bg ... <target>` records
    <target> in the state file; `serve status` reads it back; `serve reset`
    clears it."""
    stub = tmp_path / "tailscale-stub"
    log = tmp_path / "ts-argv.log"
    state = tmp_path / "ts-serve-state"
    stub.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            echo "$*" >> "{log}"
            sub="${{1:-}}"; shift || true
            case "$sub" in
              funnel)
                case "${{TS_STUB_FUNNEL:-}}" in
                  on)  echo "Funnel on:"; echo "  https://host.example.ts.net (Funnel)" ;;
                  err) echo "stub: funnel unavailable" >&2; exit 1 ;;
                  *)   echo "No serve config" ;;
                esac ;;
              status)
                if [ "${{1:-}}" = "--json" ]; then
                  printf '{{"Peer":{{"nkey:decoy":{{"DNSName":"other-peer.tailnet-abc.ts.net."}}}},"Self":{{"DNSName":"%s"}}}}\\n' "${{TS_STUB_DNSNAME:-recipe-host.tailnet-abc.ts.net.}}"
                elif [ "${{TS_STUB_STOPPED:-}}" = "1" ]; then
                  echo "Tailscale is stopped."
                else
                  echo "100.64.0.1  recipe-host  someone@example.com  linux  -"
                fi ;;
              serve)
                case "${{1:-}}" in
                  status)
                    t="$(cat "{state}" 2>/dev/null || true)"
                    if [ -n "$t" ]; then
                      echo "https://recipe-host.tailnet-abc.ts.net (tailnet only)"
                      echo "|-- / proxy $t"
                    else
                      echo "No serve config"
                    fi ;;
                  reset) : > "{state}" ;;
                  --bg)
                    for a in "$@"; do target="$a"; done
                    printf '%s\\n' "$target" > "{state}"
                    echo "Serve started." ;;
                  *) echo "stub: unknown serve args: $*" >&2; exit 1 ;;
                esac ;;
              *) echo "stub: unknown command: $sub $*" >&2; exit 1 ;;
            esac
            """
        )
    )
    stub.chmod(0o755)
    return (
        {"RECIPE_DEPLOY_TAILSCALE_BIN": str(stub), "TS_STUB_DNSNAME": "recipe-host.tailnet-abc.ts.net."},
        log,
        state,
    )


def test_net_check_passes_for_a_loopback_deployment_and_a_clean_tailnet(deploy_env, ts_stub):
    env_patch, _log, _state = ts_stub
    env = {**deploy_env, **env_patch}
    assert _run(INSTALL, "--skip-build", env=env).returncode == 0
    assert _run(CONTROL, "start", env=env).returncode == 0
    assert _wait_health()
    # Serve is configured through the script the operator runs.
    assert _run(TAILSCALE_SERVE, "apply", env=env).returncode == 0

    result = _run(NET_CHECK, env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"app answers on 127.0.0.1:{PORT}" in result.stdout
    assert "bound on loopback only" in result.stdout
    assert f"Serve proxies the tailnet to http://127.0.0.1:{PORT}" in result.stdout
    assert "Funnel is off" in result.stdout
    assert "https://recipe-host.tailnet-abc.ts.net/" in result.stdout
    assert "all ingress checks passed" in result.stdout

    assert _run(CONTROL, "stop", env=env).returncode == 0


def test_net_check_fails_when_funnel_is_on(deploy_env, ts_stub):
    env_patch, _log, _state = ts_stub
    env = {**deploy_env, **env_patch, "TS_STUB_FUNNEL": "on"}
    assert _run(INSTALL, "--skip-build", env=env).returncode == 0
    assert _run(CONTROL, "start", env=env).returncode == 0
    assert _wait_health()

    result = _run(NET_CHECK, env=env)
    assert result.returncode != 0
    assert "Funnel is ON" in result.stdout
    assert "ingress checks FAILED" in result.stdout

    assert _run(CONTROL, "stop", env=env).returncode == 0


def test_net_check_fails_when_funnel_state_is_unknowable(deploy_env, ts_stub):
    # `funnel status` erroring is not "off" — check 5 must fail rather than
    # report no public exposure it could not confirm.
    env_patch, _log, _state = ts_stub
    env = {**deploy_env, **env_patch, "TS_STUB_FUNNEL": "err"}
    assert _run(INSTALL, "--skip-build", env=env).returncode == 0
    assert _run(CONTROL, "start", env=env).returncode == 0
    assert _wait_health()

    result = _run(NET_CHECK, env=env)
    assert result.returncode != 0
    assert "could not determine Funnel state" in result.stdout

    assert _run(CONTROL, "stop", env=env).returncode == 0


def test_net_check_flags_a_non_loopback_listener_on_the_app_port(deploy_env, ts_stub):
    # A listener bound to 0.0.0.0 on the app port is a LAN/public bypass of the
    # Tailscale ingress — net-check must catch it. No app is started here; the
    # bind itself is what the check inspects.
    env_patch, _log, _state = ts_stub
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", 0))
    srv.listen(1)
    bypass_port = srv.getsockname()[1]
    try:
        env = {**deploy_env, **env_patch, "RECIPE_DEPLOY_PORT": str(bypass_port)}
        result = _run(NET_CHECK, "--local-only", env=env)
        assert result.returncode != 0
        assert f"non-loopback listener on port {bypass_port}" in result.stdout
    finally:
        srv.close()


def test_net_check_local_only_skips_tailscale_and_needs_no_cli(deploy_env, tmp_path: Path):
    env = {
        **deploy_env,
        "RECIPE_DEPLOY_TAILSCALE_BIN": str(tmp_path / "no-such-tailscale"),
    }
    assert _run(INSTALL, "--skip-build", env=env).returncode == 0
    assert _run(CONTROL, "start", env=env).returncode == 0
    assert _wait_health()

    result = _run(NET_CHECK, "--local-only", env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "bound on loopback only" in result.stdout
    assert "Tailscale checks skipped" in result.stdout
    assert "Serve proxies" not in result.stdout

    assert _run(CONTROL, "stop", env=env).returncode == 0


def test_tailscale_serve_apply_points_serve_at_the_local_origin(deploy_env, ts_stub):
    env_patch, log, _state = ts_stub
    env = {**deploy_env, **env_patch}
    assert _run(INSTALL, "--skip-build", env=env).returncode == 0
    assert _run(CONTROL, "start", env=env).returncode == 0
    assert _wait_health()

    result = _run(TAILSCALE_SERVE, "apply", env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    # HTTPS on the tailnet, background/persistent, pointed at the loopback origin.
    argv = log.read_text()
    assert f"serve --bg --https=443 http://127.0.0.1:{PORT}" in argv
    # apply echoes the resulting mapping and the tailnet URL.
    assert f"127.0.0.1:{PORT}" in result.stdout
    assert "https://recipe-host.tailnet-abc.ts.net/" in result.stdout

    # The mapping is now visible through `status`.
    status = _run(TAILSCALE_SERVE, "status", env=env)
    assert status.returncode == 0
    assert f"127.0.0.1:{PORT}" in status.stdout
    assert "Funnel           : off" in status.stdout

    assert _run(CONTROL, "stop", env=env).returncode == 0


def test_tailscale_serve_apply_refuses_when_funnel_is_on(deploy_env, ts_stub):
    env_patch, log, _state = ts_stub
    env = {**deploy_env, **env_patch, "TS_STUB_FUNNEL": "on"}
    assert _run(INSTALL, "--skip-build", env=env).returncode == 0
    assert _run(CONTROL, "start", env=env).returncode == 0
    assert _wait_health()

    result = _run(TAILSCALE_SERVE, "apply", env=env)
    assert result.returncode != 0
    assert "Funnel is active" in result.stderr
    assert "serve --bg" not in log.read_text()  # nothing was configured

    assert _run(CONTROL, "stop", env=env).returncode == 0


def test_tailscale_serve_apply_refuses_without_a_local_origin(deploy_env, ts_stub):
    # No deployment started: apply must not configure an ingress to a dead port.
    env_patch, log, _state = ts_stub
    env = {**deploy_env, **env_patch}
    result = _run(TAILSCALE_SERVE, "apply", env=env)
    assert result.returncode != 0
    assert "not answering /api/health" in result.stderr
    assert not log.exists() or "serve --bg" not in log.read_text()


def test_tailscale_serve_url_prints_the_magicdns_https_url(deploy_env, ts_stub):
    env_patch, _log, _state = ts_stub
    env = {**deploy_env, **env_patch, "TS_STUB_DNSNAME": "recipe-host.tailnet-9zzz.ts.net."}
    result = _run(TAILSCALE_SERVE, "url", env=env)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "https://recipe-host.tailnet-9zzz.ts.net/"


# --- deploy/backup-run.sh (private-household-deployment ticket 07a) ---------
#
# The command a scheduler runs for an unattended daily snapshot. On the target
# host that is Windows Task Scheduler, via
#   wsl.exe -d <distro> -- bash <checkout>/deploy/backup-run.sh
# registered by deploy/windows/register-backup-task.ps1. Driven here exactly as
# the scheduler would — as a subprocess, no terminal, and (in one case) no
# running app — against disposable data. Real Task Scheduler registration and
# the reboot-without-login check are the actual-host acceptance gate recorded in
# .scratch/private-household-deployment/host-acceptance-07a.md.

BACKUP_RUN = REPO_ROOT / "deploy" / "backup-run.sh"


def _backup_log_lines(tmp_path: Path) -> list[str]:
    log = tmp_path / "data" / "run" / "backup-runs.log"
    return log.read_text().splitlines() if log.is_file() else []


def _clear_snapshots(tmp_path: Path) -> None:
    """Drop the adoption snapshot so a following backup-run leaves exactly one
    file — avoids depending on the wall clock to disambiguate same-second
    snapshot names (`create_backup` names to the second)."""
    for p in (tmp_path / "data" / "backups").glob("recipe-*.db"):
        p.unlink()


def _only_snapshot(tmp_path: Path) -> Path:
    (snap,) = (tmp_path / "data" / "backups").glob("recipe-*.db")
    return snap


def test_backup_run_snapshots_a_running_deployment(deploy_env, tmp_path: Path):
    dev_db = tmp_path / "dev.db"
    _seed_db(dev_db, ["SCHEDULED SNAPSHOT"])
    assert _run(INSTALL, "--skip-build", "--adopt-from", str(dev_db), env=deploy_env).returncode == 0
    assert _run(CONTROL, "start", env=deploy_env).returncode == 0
    assert _wait_health()
    _clear_snapshots(tmp_path)

    result = _run(BACKUP_RUN, env=deploy_env)
    assert result.returncode == 0, result.stderr + result.stdout

    # One new timestamped snapshot, a usable copy of the live database.
    assert _snapshot_count(tmp_path) == 1
    assert _recipe_titles(_only_snapshot(tmp_path)) == ["SCHEDULED SNAPSHOT"]

    # The run is recorded for diagnostics (07b builds freshness reporting on it).
    lines = _backup_log_lines(tmp_path)
    assert len(lines) == 1
    assert re.match(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ ok .*/recipe-\d{8}T\d{6}Z\.db$", lines[0]
    ), lines[0]
    assert str(_only_snapshot(tmp_path)) in lines[0]

    assert _run(CONTROL, "stop", env=deploy_env).returncode == 0


def test_backup_run_works_with_the_app_stopped(deploy_env, tmp_path: Path):
    # Independent of app supervision: no `control.sh start`, no server process.
    dev_db = tmp_path / "dev.db"
    _seed_db(dev_db, ["SNAPSHOT WITHOUT A SERVER"])
    assert _run(INSTALL, "--skip-build", "--adopt-from", str(dev_db), env=deploy_env).returncode == 0
    _clear_snapshots(tmp_path)

    result = _run(BACKUP_RUN, env=deploy_env)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "app supervision not required" in result.stdout

    assert _snapshot_count(tmp_path) == 1
    assert _recipe_titles(_only_snapshot(tmp_path)) == ["SNAPSHOT WITHOUT A SERVER"]
    assert _backup_log_lines(tmp_path)[-1].split()[1] == "ok"


def test_backup_run_fails_without_a_database_and_preserves_earlier_snapshots(
    deploy_env, tmp_path: Path
):
    backups = tmp_path / "data" / "backups"
    backups.mkdir(parents=True)
    prior = backups / "recipe-20200101T000000Z.db"
    prior.write_bytes(b"earlier good snapshot")

    # Install with no source database: none is created (deferred to first start).
    assert _run(
        INSTALL, "--skip-build", "--adopt-from", str(tmp_path / "missing.db"), env=deploy_env
    ).returncode == 0
    assert not (tmp_path / "data" / "recipe.db").exists()

    result = _run(BACKUP_RUN, env=deploy_env)
    assert result.returncode != 0
    assert "does not exist" in result.stderr

    # The earlier snapshot is untouched; nothing new was published.
    assert prior.read_bytes() == b"earlier good snapshot"
    assert list(backups.glob("recipe-*.db")) == [prior]
    assert _backup_log_lines(tmp_path)[-1].split()[1] == "FAIL"


def test_backup_run_fails_when_the_destination_cannot_be_written(deploy_env, tmp_path: Path):
    dev_db = tmp_path / "dev.db"
    _seed_db(dev_db, ["KEPT"])
    assert _run(INSTALL, "--skip-build", "--adopt-from", str(dev_db), env=deploy_env).returncode == 0

    # A backup directory whose parent is a regular file: it cannot be created.
    (tmp_path / "blocker").write_text("not a directory")
    env = {**deploy_env, "RECIPE_DEPLOY_BACKUP_DIR": str(tmp_path / "blocker" / "backups")}

    result = _run(BACKUP_RUN, env=env)
    assert result.returncode != 0
    assert _backup_log_lines(tmp_path)[-1].split()[1] == "FAIL"


def test_backup_run_is_time_bounded(deploy_env, tmp_path: Path):
    # A snapshot that never returns must not wedge the scheduled task. Stub the
    # snapshot's `uv` with a sleeper and set a 1s ceiling.
    backups = tmp_path / "data" / "backups"
    backups.mkdir(parents=True)
    prior = backups / "recipe-20200101T000000Z.db"
    prior.write_bytes(b"earlier good snapshot")
    (tmp_path / "data" / "recipe.db").write_bytes(b"SQLite format 3\x00")  # the -f check passes

    sleeper = tmp_path / "uv-sleeper"
    sleeper.write_text("#!/usr/bin/env bash\nsleep 10\n")
    sleeper.chmod(0o755)
    env = {
        **deploy_env,
        "RECIPE_DEPLOY_UV_BIN": str(sleeper),
        "RECIPE_DEPLOY_BACKUP_TIMEOUT": "1",
    }

    start = time.time()
    result = _run(BACKUP_RUN, env=env)
    assert time.time() - start < 8  # it did not wait out the sleeper
    assert result.returncode != 0
    assert "time limit" in result.stderr
    assert prior.read_bytes() == b"earlier good snapshot"
    assert _backup_log_lines(tmp_path)[-1].split()[1] == "FAIL"


def test_backup_run_applies_retention_after_a_successful_snapshot(deploy_env, tmp_path: Path):
    # 07b: once the new snapshot is safely published, the job keeps the newest
    # RECIPE_DEPLOY_BACKUP_KEEP valid snapshots and drops older ones.
    dev_db = tmp_path / "dev.db"
    _seed_db(dev_db, ["RETAINED"])
    assert _run(INSTALL, "--skip-build", "--adopt-from", str(dev_db), env=deploy_env).returncode == 0
    _clear_snapshots(tmp_path)

    backups = tmp_path / "data" / "backups"
    older = [
        backups / "recipe-20200101T000000Z.db",
        backups / "recipe-20200102T000000Z.db",
        backups / "recipe-20200103T000000Z.db",
    ]
    for path in older:
        _seed_db(path, ["OLD"])

    env = {**deploy_env, "RECIPE_DEPLOY_BACKUP_KEEP": "2"}
    result = _run(BACKUP_RUN, env=env)
    assert result.returncode == 0, result.stderr + result.stdout

    remaining = {p.name for p in backups.glob("recipe-*.db")}
    assert len(remaining) == 2  # the fresh snapshot + the newest pre-existing one
    assert "recipe-20200103T000000Z.db" in remaining
    assert not older[0].exists() and not older[1].exists()
    assert _backup_log_lines(tmp_path)[-1].split()[1] == "ok"


def test_status_reports_the_backup_schedule_inputs(deploy_env):
    assert _run(INSTALL, "--skip-build", env=deploy_env).returncode == 0
    status = _run(CONTROL, "status", env=deploy_env)
    assert "backup run log   :" in status.stdout
    assert "backup job limit :" in status.stdout
    assert "backup retention :" in status.stdout
    assert "backup freshness :" in status.stdout


# --- recover the deployment from a scheduled snapshot (private-household-
#     deployment ticket 07c) ----------------------------------------------------
#
# Runbook 15 ties the unattended snapshot job (07a) and the in-place database
# replace (02c) into one deployment-recovery procedure: select the newest good
# scheduled snapshot, stop writers, preserve the live database, replace it,
# restart, and confirm household access. Driven here end to end against the
# isolated `deploy_env` deployment — its own port, data/backup/runtime dirs, and
# app process — so live household data is never touched. Registration is opened
# only to seed records, then closed for the recovery assertions. The timed
# actual-host rehearsal (real browser, within the one-day target) is the
# acceptance gate in host-acceptance-07c.md.

RESTORE_PY = REPO_ROOT / "backend" / "scripts" / "restore.py"
RECOVERY_CODE = "recovery-rehearsal-code"
MEMBER_PW = "correct horse battery staple"


def _api(
    method: str,
    path: str,
    port: str = PORT,
    *,
    token: str | None = None,
    body: dict | None = None,
):
    """One JSON call to the running deployment. Returns (status, parsed body|None)."""
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        return exc.code, None


def _register(username: str) -> str:
    status, data = _api(
        "POST",
        "/api/auth/register",
        body={"username": username, "password": MEMBER_PW, "code": RECOVERY_CODE},
    )
    assert status == 201, (status, data)
    return data["token"]


def _create_recipe(token: str, title: str) -> None:
    status, _ = _api(
        "POST",
        "/api/recipes",
        token=token,
        body={"title": title, "tags": [], "steps": [], "ingredients": []},
    )
    assert status == 201, status


def _titles_via_http(token: str) -> list[str]:
    status, data = _api("GET", "/api/recipes", token=token)
    assert status == 200, status
    return sorted(r["title"] for r in data)


def _restore_replace(snapshot: Path, target: Path, preserve_dir: Path, env: dict):
    return subprocess.run(
        [
            sys.executable,
            str(RESTORE_PY),
            "--replace",
            "--snapshot", str(snapshot),
            "--target", str(target),
            "--preserve-dir", str(preserve_dir),
        ],
        cwd=str(REPO_ROOT / "backend"),
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )


def _add_recipe_row(path: Path, title: str) -> None:
    """Append one recipe straight to an app-schema database (a divergence that
    needs no running app)."""
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as conn:
        conn.execute(insert(models.Recipe).values(**_recipe_row(title)))
    engine.dispose()


def test_recover_deployment_from_a_scheduled_snapshot(deploy_env, tmp_path: Path):
    # Registration is opened only to seed household records through the API,
    # then closed for the recovery assertions.
    reg_env = {
        **deploy_env,
        "RECIPE_ALLOW_REGISTRATION": "1",
        "RECIPE_REGISTRATION_CODE": RECOVERY_CODE,
    }
    assert _run(INSTALL, "--skip-build", env=reg_env).returncode == 0
    assert _run(CONTROL, "start", env=reg_env).returncode == 0
    assert _wait_health()

    token = _register("alice")
    _create_recipe(token, "Pre-snapshot Stew")

    assert _snapshot_count(tmp_path) == 0  # no adoption snapshot without --adopt-from
    assert _run(BACKUP_RUN, env=deploy_env).returncode == 0
    assert _backup_log_lines(tmp_path)[-1].split()[1] == "ok"
    scheduled = _only_snapshot(tmp_path)
    scheduled_before = scheduled.read_bytes()

    # A change committed after the snapshot — recovery must roll it back.
    _create_recipe(token, "Post-snapshot Pie")

    # stop writers -> preserve + replace -> restart, registration now closed.
    assert _run(CONTROL, "stop", env=reg_env).returncode == 0
    deployment_db = tmp_path / "data" / "recipe.db"
    result = _restore_replace(
        scheduled, deployment_db, tmp_path / "pre-restore", deploy_env
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "restore ok: replaced" in result.stdout
    assert "preserved prior database:" in result.stdout

    assert _run(CONTROL, "start", env=deploy_env).returncode == 0
    assert _wait_health()
    # Runbook 15 step 5: the listener is still loopback-only after the restart.
    assert _run(NET_CHECK, "--local-only", env=deploy_env).returncode == 0

    # Household access: a fresh login works and sees the snapshot's world.
    status, data = _api(
        "POST", "/api/auth/login", body={"username": "alice", "password": MEMBER_PW}
    )
    assert status == 200, (status, data)
    assert _titles_via_http(data["token"]) == ["Pre-snapshot Stew"]  # no Post-snapshot Pie

    # The session captured before recovery is dead — restored sessions cleared.
    assert _api("GET", "/api/auth/me", token=token)[0] == 401

    # Registration really is closed again on the recovered deployment.
    assert (
        _api(
            "POST",
            "/api/auth/register",
            body={"username": "mallory", "password": MEMBER_PW, "code": RECOVERY_CODE},
        )[0]
        == 403
    )

    # The scheduled snapshot restored from is only read; live data was never in
    # reach (the isolated deployment owns every path).
    assert scheduled.read_bytes() == scheduled_before
    assert not (REPO_ROOT / "backend" / "recipe.db").exists()

    assert _run(CONTROL, "stop", env=deploy_env).returncode == 0


def test_recovery_selects_the_newest_good_scheduled_snapshot(deploy_env, tmp_path: Path):
    # Runbook 15 step 1: pick the newest `ok` line from backup-runs.log even when
    # a later scheduled run FAILed, then replace in place from it. No running app.
    dev_db = tmp_path / "dev.db"
    _seed_db(dev_db, ["Pre-snapshot Stew"])
    assert _run(INSTALL, "--skip-build", "--adopt-from", str(dev_db), env=deploy_env).returncode == 0
    deployment_db = tmp_path / "data" / "recipe.db"
    _clear_snapshots(tmp_path)  # drop the adoption snapshot

    # One good scheduled run...
    assert _run(BACKUP_RUN, env=deploy_env).returncode == 0
    good = _only_snapshot(tmp_path)

    # ...then a later run that FAILs — the database is moved aside for it, so the
    # log ends `ok <good>` then `FAIL <reason>`.
    deployment_db.rename(tmp_path / "recipe.db.moved")
    assert _run(BACKUP_RUN, env=deploy_env).returncode != 0
    (tmp_path / "recipe.db.moved").rename(deployment_db)
    tail = [line.split()[1] for line in _backup_log_lines(tmp_path)[-2:]]
    assert tail == ["ok", "FAIL"], _backup_log_lines(tmp_path)

    # The runbook's selection command picks the newest good snapshot.
    picked = subprocess.run(
        [
            "awk",
            '$2 == "ok" { p = $3 } END { print p }',
            str(tmp_path / "data" / "run" / "backup-runs.log"),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert Path(picked) == good

    # Diverge, then restore in place from the picked snapshot.
    _add_recipe_row(deployment_db, "Post-snapshot Pie")
    preserve_dir = tmp_path / "pre-restore"
    result = _restore_replace(Path(picked), deployment_db, preserve_dir, deploy_env)
    assert result.returncode == 0, result.stderr + result.stdout

    assert _recipe_titles(deployment_db) == ["Pre-snapshot Stew"]  # divergence rolled back
    # The replaced database is kept as a recovery point — the divergence is not lost.
    (preserved,) = preserve_dir.glob("recipe-*.db")
    assert "Post-snapshot Pie" in _recipe_titles(preserved)
# --- deploy/supervise.sh (private-household-deployment ticket 06a) ----------
#
# Automatic app-process recovery: a watch loop around deploy/control.sh that
# restarts the app if it exits while the WSL distribution stays up. Driven the
# way an operator runs it — subprocesses against disposable data, this harness
# owning every process it starts (the `deploy_env` teardown stops the
# supervisor before the app). These cases run on their own port so a detached
# watch loop cannot collide with the other deployment tests (or a parallel
# worktree) on the shared PORT. Real Windows/WSL process-recovery is the
# actual-host acceptance gate recorded in
# .scratch/private-household-deployment/host-acceptance-06a.md.

SUPERVISE_PORT = "8763"
RUN_DIR = ("data", "run")
APP_PIDFILE = (*RUN_DIR, "recipe.pid")
SUPERVISOR_PIDFILE = (*RUN_DIR, "recipe-supervisor.pid")
SUPERVISOR_LOG = (*RUN_DIR, "recipe-supervisor.log")


@pytest.fixture
def supervise_env(deploy_env):
    """`deploy_env` on its own port and with a snappy supervision cadence, so
    restart assertions neither wait on the production 3s poll nor share the
    fixed PORT with the other deployment tests."""
    return {
        **deploy_env,
        "RECIPE_DEPLOY_PORT": SUPERVISE_PORT,
        "RECIPE_DEPLOY_SUPERVISE_INTERVAL": "1",
        "RECIPE_DEPLOY_SUPERVISE_BACKOFF_MAX": "3",
    }


def _read_pid(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_for(predicate, timeout: float = 30.0, interval: float = 0.3) -> bool:
    """Poll `predicate` until it returns truthy or `timeout` elapses. A
    predicate that raises (e.g. reads a file the supervisor has not created
    yet) counts as not-ready, not as a test error."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def _provision_account(db_path: Path, username: str, password: str) -> None:
    """Create one household login directly in a stopped deployment's database
    (the operator path from ticket 03a) so a supervise test can sign in through
    the restarted origin."""
    result = subprocess.run(
        ["uv", "run", "python", "scripts/provision.py",
         "--database-url", f"sqlite:///{db_path}", "--accounts", "-"],
        cwd=str(REPO_ROOT / "backend"),
        input=f"{username} {password}\n",
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stderr + result.stdout


def _new_app_pid(tmp_path: Path, previous: int, timeout: float = 30) -> int:
    """Wait until recipe.pid names a live process other than `previous`; return it."""
    assert _wait_for(
        lambda: (p := _read_pid(tmp_path.joinpath(*APP_PIDFILE))) not in (None, previous)
        and _pid_alive(p),
        timeout=timeout,
    )
    return _read_pid(tmp_path.joinpath(*APP_PIDFILE))


def test_supervise_restarts_a_terminated_app_and_records_stay_usable(
    supervise_env, tmp_path: Path
):
    dev_db = tmp_path / "dev.db"
    _seed_db(dev_db, ["SUPERVISED RECORD"])
    assert _run(INSTALL, "--skip-build", "--adopt-from", str(dev_db), env=supervise_env).returncode == 0

    deployment_db = tmp_path / "data" / "recipe.db"
    _provision_account(deployment_db, "chef", "cook-the-books-2026")

    assert _run(SUPERVISE, "start", env=supervise_env).returncode == 0
    assert _wait_health(30, SUPERVISE_PORT)
    first_pid = _read_pid(tmp_path.joinpath(*APP_PIDFILE))
    assert first_pid and _pid_alive(first_pid)

    # A household member is signed in and using the app through the origin.
    st, payload = _api(
        "POST", "/api/auth/login", SUPERVISE_PORT,
        body={"username": "chef", "password": "cook-the-books-2026"},
    )
    assert st == 200, payload
    token = payload["token"]
    st, recipes = _api("GET", "/api/recipes", SUPERVISE_PORT, token=token)
    assert st == 200 and [r["title"] for r in recipes] == ["SUPERVISED RECORD"]

    # Simulate a process failure: kill the whole app process group.
    os.killpg(first_pid, signal.SIGKILL)
    assert _wait_for(lambda: not _pid_alive(first_pid), timeout=10)

    # The supervisor brings it back unaided — a new process, health restored.
    second_pid = _new_app_pid(tmp_path, first_pid)
    assert _wait_health(30, SUPERVISE_PORT)
    assert second_pid != first_pid

    # Local API access is back on the same explicit database: the saved record is
    # still readable, the existing session still works, and a new write persists.
    st, recipes = _api("GET", "/api/recipes", SUPERVISE_PORT, token=token)
    assert st == 200 and [r["title"] for r in recipes] == ["SUPERVISED RECORD"]
    st, _ = _api(
        "POST", "/api/recipes", SUPERVISE_PORT, token=token,
        body={"title": "ADDED AFTER RESTART"},
    )
    assert st == 201
    assert _recipe_titles(deployment_db) == ["ADDED AFTER RESTART", "SUPERVISED RECORD"]

    status = _run(SUPERVISE, "status", env=supervise_env)
    assert status.returncode == 0
    assert re.search(r"supervisor\s*:\s*running \(pid \d+\)", status.stdout)
    assert re.search(r"app restarts\s*:\s*[1-9]", status.stdout)

    # stop takes the supervisor and the app down together.
    assert _run(SUPERVISE, "stop", env=supervise_env).returncode == 0
    assert _run(CONTROL, "status", env=supervise_env).returncode == 3
    assert re.search(
        r"supervisor\s*:\s*stopped", _run(SUPERVISE, "status", env=supervise_env).stdout
    )


def test_supervise_start_refuses_a_second_supervisor_and_never_duplicates_the_app(
    supervise_env, tmp_path: Path
):
    assert _run(INSTALL, "--skip-build", env=supervise_env).returncode == 0
    assert _run(SUPERVISE, "start", env=supervise_env).returncode == 0
    assert _wait_health(port=SUPERVISE_PORT)
    app_pid = _read_pid(tmp_path.joinpath(*APP_PIDFILE))
    sup_pid = _read_pid(tmp_path.joinpath(*SUPERVISOR_PIDFILE))
    assert sup_pid and _pid_alive(sup_pid)

    dup = _run(SUPERVISE, "start", env=supervise_env)
    assert dup.returncode != 0
    assert "already supervising" in dup.stderr

    # Same single supervisor loop, same app pid — nothing was duplicated.
    assert _read_pid(tmp_path.joinpath(*SUPERVISOR_PIDFILE)) == sup_pid
    assert _read_pid(tmp_path.joinpath(*APP_PIDFILE)) == app_pid
    assert _wait_health(5, SUPERVISE_PORT)

    assert _run(SUPERVISE, "stop", env=supervise_env).returncode == 0


def test_supervise_adopts_an_already_running_app_without_restarting_it(
    supervise_env, tmp_path: Path
):
    assert _run(INSTALL, "--skip-build", env=supervise_env).returncode == 0
    # Operator started the app manually first (e.g. from runbook 8).
    assert _run(CONTROL, "start", env=supervise_env).returncode == 0
    assert _wait_health(port=SUPERVISE_PORT)
    manual_pid = _read_pid(tmp_path.joinpath(*APP_PIDFILE))

    started = _run(SUPERVISE, "start", env=supervise_env)
    assert started.returncode == 0, started.stderr + started.stdout
    assert "supervising it in place" in started.stdout
    # Not restarted: same pid, zero restarts recorded.
    assert _read_pid(tmp_path.joinpath(*APP_PIDFILE)) == manual_pid
    assert re.search(
        r"app restarts\s*:\s*0", _run(SUPERVISE, "status", env=supervise_env).stdout
    )

    # It is genuinely supervising: kill the adopted app, it returns.
    os.killpg(manual_pid, signal.SIGKILL)
    _new_app_pid(tmp_path, manual_pid)
    assert _wait_health(30, SUPERVISE_PORT)

    assert _run(SUPERVISE, "stop", env=supervise_env).returncode == 0


def test_supervise_stop_is_clean_when_nothing_is_supervised(supervise_env):
    assert _run(INSTALL, "--skip-build", env=supervise_env).returncode == 0
    result = _run(SUPERVISE, "stop", env=supervise_env)
    assert result.returncode == 0
    assert "no supervisor running" in result.stdout


def test_supervise_run_foreground_supervises_until_signalled(supervise_env, tmp_path: Path):
    assert _run(INSTALL, "--skip-build", env=supervise_env).returncode == 0
    proc = subprocess.Popen(
        ["bash", str(SUPERVISE), "run"],
        env=supervise_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        assert _wait_health(30, SUPERVISE_PORT)
        # `run` starts the app synchronously *before* the watch loop takes over.
        # Wait for the loop to own its pidfile before killing the app, so the
        # kill can't race that initial `control.sh start`'s own health check.
        assert _wait_for(
            lambda: _read_pid(tmp_path.joinpath(*SUPERVISOR_PIDFILE)), timeout=10
        )
        app_pid = _read_pid(tmp_path.joinpath(*APP_PIDFILE))
        assert app_pid

        os.killpg(app_pid, signal.SIGKILL)
        _new_app_pid(tmp_path, app_pid)
        assert _wait_health(30, SUPERVISE_PORT)

        # SIGTERM to the foreground supervisor stops the app with it.
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=30) == 0
        assert _run(CONTROL, "status", env=supervise_env).returncode == 3
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)
        _run(SUPERVISE, "stop", env=supervise_env)
        _run(CONTROL, "stop", env=supervise_env)


def test_supervise_keeps_retrying_a_failed_restart_then_recovers(supervise_env, tmp_path: Path):
    assert _run(INSTALL, "--skip-build", env=supervise_env).returncode == 0
    assert _run(SUPERVISE, "start", env=supervise_env).returncode == 0
    assert _wait_health(port=SUPERVISE_PORT)
    app_pid = _read_pid(tmp_path.joinpath(*APP_PIDFILE))
    assert app_pid

    # Break the next start by moving the build away, then kill the app.
    dist = Path(supervise_env["RECIPE_DEPLOY_FRONTEND_DIST"])
    stashed = tmp_path / "stashed-dist"
    shutil.move(str(dist), str(stashed))
    os.killpg(app_pid, signal.SIGKILL)

    log_path = tmp_path.joinpath(*SUPERVISOR_LOG)
    # The supervisor reports the failed restart and does not give up.
    assert _wait_for(
        lambda: "restart #" in log_path.read_text() and "failed" in log_path.read_text(),
        timeout=20,
    )
    down = _run(SUPERVISE, "status", env=supervise_env)
    assert down.returncode == 3  # app still down (control.sh status exit code)
    assert re.search(r"supervisor\s*:\s*running", down.stdout)

    # Restore the build; the supervisor recovers on its own (backoff is capped).
    shutil.move(str(stashed), str(dist))
    assert _wait_health(30, SUPERVISE_PORT)
    assert _read_pid(tmp_path.joinpath(*APP_PIDFILE)) not in (None, app_pid)

    assert _run(SUPERVISE, "stop", env=supervise_env).returncode == 0


# --- deploy/wsl-keeper.sh (private-household-deployment ticket 06b) ---------
#
# WSL lifetime: the one long-lived foreground process a Windows Scheduled Task
# runs through `wsl.exe -d <distro> -- ...`. While it runs the distribution
# stays up; it holds exactly one deploy/supervise.sh (06a) above the app and
# re-launches it if it disappears. Driven here the way Task Scheduler runs it —
# a `run` subprocess this harness owns, against disposable data on the supervise
# port. The real `wsl.exe` invocation, the Windows task and its power settings,
# and recovery across an actual `wsl --shutdown` are the actual-host acceptance
# gate recorded in .scratch/private-household-deployment/host-acceptance-06b.md.

KEEPER_PIDFILE = (*RUN_DIR, "recipe-keeper.pid")
KEEPER_LOG = (*RUN_DIR, "recipe-keeper.log")


@pytest.fixture
def keeper_env(supervise_env):
    """`supervise_env` with a fast keeper heartbeat so the watchdog assertions
    do not wait on the production 30s cadence."""
    return {**supervise_env, "RECIPE_DEPLOY_KEEPER_HEARTBEAT": "1"}


@contextlib.contextmanager
def _keeper_run(env: dict):
    """`wsl-keeper.sh run` as Task Scheduler launches it — a foreground process
    this test owns. Always torn down (SIGTERM, then a stop sweep)."""
    proc = subprocess.Popen(
        ["bash", str(KEEPER), "run"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        yield proc
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)
        _run(KEEPER, "stop", env=env)
        _run(CONTROL, "stop", env=env)


def test_keeper_run_holds_the_app_up_and_stop_takes_it_all_down(
    keeper_env, tmp_path: Path
):
    assert _run(INSTALL, "--skip-build", env=keeper_env).returncode == 0

    with _keeper_run(keeper_env) as proc:
        assert _wait_health(30, SUPERVISE_PORT)
        # keeper and supervisor each own their own pidfile.
        assert _wait_for(
            lambda: _read_pid(tmp_path.joinpath(*KEEPER_PIDFILE))
            and _read_pid(tmp_path.joinpath(*SUPERVISOR_PIDFILE)),
            timeout=15,
        )
        keeper_pid = _read_pid(tmp_path.joinpath(*KEEPER_PIDFILE))
        assert keeper_pid and _pid_alive(keeper_pid)
        app_pid = _read_pid(tmp_path.joinpath(*APP_PIDFILE))
        assert app_pid

        # An app crash is absorbed by the supervisor beneath the keeper.
        os.killpg(app_pid, signal.SIGKILL)
        second_pid = _new_app_pid(tmp_path, app_pid)
        assert _wait_health(30, SUPERVISE_PORT)
        assert second_pid != app_pid
        assert _pid_alive(keeper_pid)  # keeper itself untouched

        status = _run(KEEPER, "status", env=keeper_env)
        assert status.returncode == 0
        assert re.search(r"keeper\s*:\s*running \(pid \d+\)", status.stdout)

        # SIGTERM (Task Scheduler "End task") stops the supervisor, the app, and
        # the keeper together, and exits 0.
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=30) == 0

    assert _run(CONTROL, "status", env=keeper_env).returncode == 3
    assert not _pid_alive(keeper_pid)
    assert re.search(
        r"keeper\s*:\s*stopped", _run(KEEPER, "status", env=keeper_env).stdout
    )


def test_keeper_run_refuses_a_second_keeper_and_never_duplicates(
    keeper_env, tmp_path: Path
):
    assert _run(INSTALL, "--skip-build", env=keeper_env).returncode == 0

    with _keeper_run(keeper_env):
        assert _wait_health(30, SUPERVISE_PORT)
        assert _wait_for(
            lambda: _read_pid(tmp_path.joinpath(*KEEPER_PIDFILE)), timeout=15
        )
        keeper_pid = _read_pid(tmp_path.joinpath(*KEEPER_PIDFILE))
        sup_pid = _read_pid(tmp_path.joinpath(*SUPERVISOR_PIDFILE))
        app_pid = _read_pid(tmp_path.joinpath(*APP_PIDFILE))

        dup = _run(KEEPER, "run", env=keeper_env)
        assert dup.returncode != 0
        assert "already keeping WSL up" in dup.stderr

        # Same keeper loop, same supervisor, same app — nothing was doubled.
        assert _read_pid(tmp_path.joinpath(*KEEPER_PIDFILE)) == keeper_pid
        assert _read_pid(tmp_path.joinpath(*SUPERVISOR_PIDFILE)) == sup_pid
        assert _read_pid(tmp_path.joinpath(*APP_PIDFILE)) == app_pid
        assert _wait_health(5, SUPERVISE_PORT)


def test_keeper_relaunches_a_terminated_supervisor_without_duplicating_the_app(
    keeper_env, tmp_path: Path
):
    assert _run(INSTALL, "--skip-build", env=keeper_env).returncode == 0

    with _keeper_run(keeper_env):
        assert _wait_health(30, SUPERVISE_PORT)
        assert _wait_for(
            lambda: _read_pid(tmp_path.joinpath(*SUPERVISOR_PIDFILE)), timeout=15
        )
        first_sup = _read_pid(tmp_path.joinpath(*SUPERVISOR_PIDFILE))
        app_pid = _read_pid(tmp_path.joinpath(*APP_PIDFILE))
        assert first_sup and app_pid

        # Hard-kill the supervisor loop (no TERM handler runs — the app it
        # started keeps running, now unsupervised).
        os.kill(first_sup, signal.SIGKILL)
        assert _wait_for(lambda: not _pid_alive(first_sup), timeout=10)

        # The keeper notices within a heartbeat and starts a fresh supervisor,
        # which adopts the still-running app rather than starting a second one.
        assert _wait_for(
            lambda: (p := _read_pid(tmp_path.joinpath(*SUPERVISOR_PIDFILE)))
            not in (None, first_sup)
            and _pid_alive(p),
            timeout=20,
        )
        assert "supervisor has gone" in tmp_path.joinpath(*KEEPER_LOG).read_text()
        assert _read_pid(tmp_path.joinpath(*APP_PIDFILE)) == app_pid
        assert _wait_health(5, SUPERVISE_PORT)

        # Still genuinely supervised: kill the app, the new supervisor restores it.
        os.killpg(app_pid, signal.SIGKILL)
        _new_app_pid(tmp_path, app_pid)
        assert _wait_health(30, SUPERVISE_PORT)


def test_keeper_stop_is_clean_when_nothing_is_running(keeper_env):
    assert _run(INSTALL, "--skip-build", env=keeper_env).returncode == 0
    result = _run(KEEPER, "stop", env=keeper_env)
    assert result.returncode == 0
    assert "no keeper running" in result.stdout
