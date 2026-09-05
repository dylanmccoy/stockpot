"""Opt-in built-frontend serving (private-household-deployment tickets 01a/01b).

`create_app` mounts the frontend's built entry document and public assets only
when `Settings.frontend_dist` is set; unset preserves the existing API-only
factory behavior every other test in this suite relies on. Real HTTP via
`TestClient` on a factory-built app — no dependency overrides, prior art:
`test_exception_handlers.py`.

Scope is deliberately narrow (see `main.py::_mount_frontend`): the entry
document at `/`, `dist/assets/*`, and (01b) a catch-all fallback to the entry
document for any other GET so a direct load/reload of a client-side route
(`/recipes/5`, `/login`, ...) works. `/api/*` and `/assets/*` are carved out of
that fallback: an unknown API path stays a plain JSON 404, and a missing asset
stays a plain 404, neither ever gets the SPA document.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import make_engine
from app.main import create_app


def _build_dist(tmp_path: Path, *, with_assets: bool = True) -> Path:
    """A minimal fake Vite build: `index.html` (+ `assets/app.js`)."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body>entry document</body></html>")
    if with_assets:
        assets = dist / "assets"
        assets.mkdir()
        (assets / "app.js").write_text("console.log('built');")
    return dist


def _app(*, frontend_dist: str | None):
    settings = Settings(database_url="sqlite://", frontend_dist=frontend_dist)
    engine = make_engine(settings.database_url)
    return create_app(settings, engine), engine


def test_frontend_dist_unset_preserves_api_only_operation() -> None:
    """The default (no `RECIPE_FRONTEND_DIST`) keeps existing API-only serving."""
    app, engine = _app(frontend_dist=None)
    try:
        with TestClient(app) as c:
            assert c.get("/api/health").json() == {"status": "ok"}
            # No frontend mounted: "/" is just an unmatched route, not an entry doc.
            assert c.get("/").status_code == 404
    finally:
        engine.dispose()


def test_frontend_dist_serves_entry_document_at_root(tmp_path: Path) -> None:
    dist = _build_dist(tmp_path)
    app, engine = _app(frontend_dist=str(dist))
    try:
        with TestClient(app) as c:
            resp = c.get("/")
            assert resp.status_code == 200
            assert "entry document" in resp.text
            assert resp.headers["content-type"].startswith("text/html")
    finally:
        engine.dispose()


def test_frontend_dist_serves_built_assets(tmp_path: Path) -> None:
    dist = _build_dist(tmp_path)
    app, engine = _app(frontend_dist=str(dist))
    try:
        with TestClient(app) as c:
            resp = c.get("/assets/app.js")
            assert resp.status_code == 200
            assert "built" in resp.text
    finally:
        engine.dispose()


def test_missing_asset_returns_404_not_the_entry_document(tmp_path: Path) -> None:
    """An unbuilt asset under `/assets` 404s rather than silently returning
    `index.html` — the `/assets` mount takes precedence over the 01b fallback."""
    dist = _build_dist(tmp_path)
    app, engine = _app(frontend_dist=str(dist))
    try:
        with TestClient(app) as c:
            resp = c.get("/assets/does-not-exist.js")
            assert resp.status_code == 404
            assert "entry document" not in resp.text
    finally:
        engine.dispose()


def test_client_side_route_serves_the_entry_document(tmp_path: Path) -> None:
    """01b: a direct load/reload of a client-side route — a real one the
    frontend router knows (`/recipes/5`), the login route, and one it doesn't
    (`/some/nonsense`, which the client's own catch-all renders as
    `NotFound`) — all get the entry document so `react-router` can take over
    rather than 404ing at the server."""
    dist = _build_dist(tmp_path)
    app, engine = _app(frontend_dist=str(dist))
    try:
        with TestClient(app) as c:
            for path in ("/recipes/5", "/login", "/some/nonsense"):
                resp = c.get(path)
                assert resp.status_code == 200, path
                assert "entry document" in resp.text
                assert resp.headers["content-type"].startswith("text/html")
    finally:
        engine.dispose()


def test_unknown_api_route_stays_a_plain_404_not_the_entry_document(
    tmp_path: Path,
) -> None:
    """01b: the fallback carves out `/api/*` — an unmatched API path keeps its
    plain JSON 404 (Starlette's default "Not Found" shape), never the SPA
    document, so a household member's stale bookmark to a removed endpoint
    doesn't silently start returning HTML."""
    dist = _build_dist(tmp_path)
    app, engine = _app(frontend_dist=str(dist))
    try:
        with TestClient(app) as c:
            resp = c.get("/api/does-not-exist")
            assert resp.status_code == 404
            assert resp.headers["content-type"].startswith("application/json")
            assert resp.json() == {"detail": "Not Found"}
    finally:
        engine.dispose()


def test_fallback_does_not_read_the_filesystem_by_request_path(
    tmp_path: Path,
) -> None:
    """Boundary case for the new catch-all: it always returns the fixed
    `index.html` and never resolves the request path against the filesystem,
    so a traversal-shaped path (percent-encoded so `TestClient` sends it
    as-is rather than collapsing it client-side) can't be used to escape the
    build directory the way a naive `dist_dir / full_path` implementation
    would allow — it just falls through to the entry document like any other
    unrecognized client-side route."""
    dist = _build_dist(tmp_path)
    secret = tmp_path / "secret.txt"
    secret.write_text("do not serve me")
    app, engine = _app(frontend_dist=str(dist))
    try:
        with TestClient(app) as c:
            for path in ("/%2e%2e/secret.txt", "/recipes/%2e%2e/%2e%2e/secret.txt"):
                resp = c.get(path)
                assert resp.status_code == 200, path
                assert "entry document" in resp.text, path
                assert "do not serve me" not in resp.text, path
    finally:
        engine.dispose()


def test_static_serving_cannot_escape_the_assets_directory(tmp_path: Path) -> None:
    """Path traversal through the `/assets` mount must not reach sibling files —
    never expose checkout/config/database contents beside the build output.

    A plain `..` segment (`/assets/../secret.txt`) never reaches the server as
    such: `httpx`/`TestClient` collapses it client-side to `/secret.txt` before
    sending, which is exactly the top-level-unknown-path shape the 01b fallback
    now legitimately answers with the entry document — not a traversal at all.
    Percent-encoding the dots is what actually exercises the mount's own
    traversal guard over the wire, so that's what this asserts against.
    """
    dist = _build_dist(tmp_path)
    secret = tmp_path / "secret.txt"
    secret.write_text("do not serve me")
    app, engine = _app(frontend_dist=str(dist))
    try:
        with TestClient(app) as c:
            for path in ("/assets/%2e%2e/secret.txt", "/assets/..%2fsecret.txt"):
                resp = c.get(path)
                assert resp.status_code == 404, path
                assert "do not serve me" not in resp.text, path
    finally:
        engine.dispose()


def test_api_routes_take_precedence_over_frontend_serving(tmp_path: Path) -> None:
    """API success/error responses are unchanged when frontend serving is on."""
    dist = _build_dist(tmp_path)
    app, engine = _app(frontend_dist=str(dist))
    try:
        with TestClient(app) as c:
            resp = c.get("/api/health")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}

            # An unauthenticated protected endpoint still gets the API's JSON
            # error shape, not the SPA document.
            resp = c.get("/api/recipes")
            assert resp.status_code == 401
            assert resp.headers["content-type"].startswith("application/json")
    finally:
        engine.dispose()


def test_missing_index_html_fails_clearly_at_startup(tmp_path: Path) -> None:
    """A build directory with no `index.html` fails fast at `create_app`, not at
    request time — the point of failing 'clearly' is that a misconfigured deploy
    never reaches the point of silently 404ing on every request."""
    empty_dir = tmp_path / "not-a-build"
    empty_dir.mkdir()
    settings = Settings(database_url="sqlite://", frontend_dist=str(empty_dir))
    engine = make_engine(settings.database_url)
    try:
        with pytest.raises(RuntimeError, match="index.html"):
            create_app(settings, engine)
    finally:
        engine.dispose()


def test_missing_frontend_dist_directory_fails_clearly(tmp_path: Path) -> None:
    does_not_exist = tmp_path / "nope"
    settings = Settings(database_url="sqlite://", frontend_dist=str(does_not_exist))
    engine = make_engine(settings.database_url)
    try:
        with pytest.raises(RuntimeError, match="index.html"):
            create_app(settings, engine)
    finally:
        engine.dispose()


def test_frontend_dist_without_assets_dir_still_serves_entry_document(
    tmp_path: Path,
) -> None:
    """An index-only build (no `assets/`) is a legal degenerate case: the entry
    document still serves, there's just nothing mounted at `/assets`."""
    dist = _build_dist(tmp_path, with_assets=False)
    app, engine = _app(frontend_dist=str(dist))
    try:
        with TestClient(app) as c:
            assert c.get("/").status_code == 200
            assert c.get("/assets/app.js").status_code == 404
    finally:
        engine.dispose()
