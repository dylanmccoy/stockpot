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
import socket
import sqlite3
import subprocess
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
