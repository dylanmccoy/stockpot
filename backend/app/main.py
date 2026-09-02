from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError

from app.config import Settings, settings
from app.database import Base, engine, make_session_factory
from app.routers import auth, recipes


def get_settings(request: Request) -> Settings:
    """Retrieve settings from the app state."""
    return request.app.state.settings


def _to_409(request: Request, exc: IntegrityError) -> JSONResponse:
    """Handle IntegrityError (unique/FK/check violations) as 409 Conflict."""
    return JSONResponse(status_code=409, content={"detail": "conflict"})


def _to_409_if_locked_else_500(request: Request, exc: OperationalError) -> JSONResponse:
    """Handle OperationalError: 409 for database locks, re-raise for others."""
    error_str = str(exc.orig)
    if "database is locked" in error_str or "database is busy" in error_str:
        return JSONResponse(status_code=409, content={"detail": "conflict"})
    raise exc


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

    app.add_exception_handler(IntegrityError, _to_409)
    app.add_exception_handler(OperationalError, _to_409_if_locked_else_500)

    # Include routers. cook_logs, inventory, grocery routers arrive in Phases 4–6.
    for r in (auth.router, recipes.router):
        app.include_router(r)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


# Module-level app for `uvicorn app.main:app`.
app = create_app(settings, engine)
