import math
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError

from app.config import Settings, settings
from app.database import Base, engine, make_session_factory
from app.routers import auth, cook_logs, grocery, inventory, recipes


def get_settings(request: Request) -> Settings:
    """Retrieve settings from the app state."""
    return request.app.state.settings


def _to_409(request: Request, exc: IntegrityError) -> JSONResponse:
    """Handle IntegrityError (unique/FK/check violations) as 409 Conflict."""
    return JSONResponse(status_code=409, content={"detail": "conflict"})


def _scrub_non_finite(value: Any) -> Any:
    """Replace non-finite floats with their repr, recursively.

    A request-validation error echoes the offending `input` back to the caller.
    When that input is `Infinity` or `NaN` — JSON literals `json.loads` accepts,
    so a client really can send them — `json.dumps` refuses to encode the error
    body and the 422 turns into an unhandled `ValueError`. Scrubbing here keeps
    the failure a 422, which is what §7 requires of every non-finite quantity.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if isinstance(value, dict):
        return {k: _scrub_non_finite(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub_non_finite(v) for v in value]
    return value


async def _validation_error_to_422(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """FastAPI's default 422 body, made encodable (spec.md §Mechanical defaults)."""
    return JSONResponse(
        status_code=422,
        content={"detail": _scrub_non_finite(jsonable_encoder(exc.errors()))},
    )


def _to_409_if_locked_else_500(request: Request, exc: OperationalError) -> JSONResponse:
    """Handle OperationalError: 409 for database locks, re-raise for others."""
    error_str = str(exc.orig)
    if "database is locked" in error_str or "database is busy" in error_str:
        return JSONResponse(status_code=409, content={"detail": "conflict"})
    raise exc


def _mount_frontend(app: FastAPI, frontend_dist: str) -> None:
    """Serve the built frontend's entry document, public assets, and the
    client-side-route fallback.

    Private-household-deployment ticket 01a (entry document + assets) and 01b
    (client-side route fallback). Registered after every API route, so
    `/api/*` always wins on a path collision. Scope is deliberately narrow:
    only `dist/index.html` and `dist/assets/*` (Vite's build output) are
    served — never the checkout, config, or database.

    `react-router`'s `<BrowserRouter>` owns client-side routes (`/login`,
    `/recipes/5`, ...): the server has no notion of them, so any GET that
    isn't `/api/*` and isn't a real built asset gets the entry document and
    lets the client router decide what to render — including its own
    catch-all `NotFound` for a path that matches nothing there either. A
    `/api/*` path with no matching route stays a plain 404 in the API's JSON
    shape, never the SPA document.
    """
    dist_dir = Path(frontend_dist)
    index_path = dist_dir / "index.html"
    if not index_path.is_file():
        raise RuntimeError(
            f"RECIPE_FRONTEND_DIST={frontend_dist!r} has no index.html "
            f"(looked for {index_path}). Build the frontend first: "
            "`cd frontend && npm run build`."
        )

    assets_dir = dist_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/", include_in_schema=False)
    def frontend_entry() -> FileResponse:
        return FileResponse(index_path)

    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend_fallback(full_path: str) -> FileResponse:
        # "api" is unreachable in practice (every real API route is matched
        # first); "assets" only matters when assets_dir doesn't exist above,
        # since a real /assets mount would already have claimed the request.
        # Kept explicit so a missing/renamed asset never falls back to the
        # entry document regardless of mount state.
        first_segment = full_path.split("/", 1)[0]
        if first_segment in ("api", "assets"):
            raise HTTPException(status_code=404)
        return FileResponse(index_path)


def create_app(settings: Settings, engine: Engine) -> FastAPI:
    """Factory to create the FastAPI app with given settings and engine."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        Base.metadata.create_all(bind=engine)
        yield

    app = FastAPI(title="Recipe API", lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = make_session_factory(engine)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    app.add_exception_handler(RequestValidationError, _validation_error_to_422)
    app.add_exception_handler(IntegrityError, _to_409)
    app.add_exception_handler(OperationalError, _to_409_if_locked_else_500)

    for r in (auth.router, recipes.router, inventory.router, cook_logs.router, grocery.router):
        app.include_router(r)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if settings.frontend_dist:
        _mount_frontend(app, settings.frontend_dist)

    return app


# Module-level app for `uvicorn app.main:app`.
app = create_app(settings, engine)
