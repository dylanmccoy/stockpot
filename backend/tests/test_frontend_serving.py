"""Opt-in built-frontend serving (private-household-deployment ticket 01a).

`create_app` mounts the frontend's built entry document and public assets only
when `Settings.frontend_dist` is set; unset preserves the existing API-only
factory behavior every other test in this suite relies on. Real HTTP via
`TestClient` on a factory-built app — no dependency overrides, prior art:
`test_exception_handlers.py`.

Scope is deliberately narrow (see `main.py::_mount_frontend`): the entry
document at `/` and `dist/assets/*`. Direct navigation/reload of a client-side
route is ticket 01b, not this one — a request like `/recipes/5` is expected to
404 here, not receive the SPA document.
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
    """No SPA fallback in this slice: an unbuilt asset, or a client-side route
    like `/recipes/5`, both 404 rather than silently returning `index.html`
    (that fallback is ticket 01b)."""
    dist = _build_dist(tmp_path)
    app, engine = _app(frontend_dist=str(dist))
    try:
        with TestClient(app) as c:
            resp = c.get("/assets/does-not-exist.js")
            assert resp.status_code == 404
            assert "entry document" not in resp.text

            resp = c.get("/recipes/5")
            assert resp.status_code == 404
            assert "entry document" not in resp.text
    finally:
        engine.dispose()


def test_static_serving_cannot_escape_the_assets_directory(tmp_path: Path) -> None:
    """Path traversal through the `/assets` mount must not reach sibling files —
    never expose checkout/config/database contents beside the build output."""
    dist = _build_dist(tmp_path)
    secret = tmp_path / "secret.txt"
    secret.write_text("do not serve me")
    app, engine = _app(frontend_dist=str(dist))
    try:
        with TestClient(app) as c:
            resp = c.get("/assets/../secret.txt")
            assert resp.status_code == 404
            assert "do not serve me" not in resp.text
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
