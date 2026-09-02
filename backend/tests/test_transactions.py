"""Transaction ownership: `TransactionRoute` owns the commit (spec.md §3.2, §6).

Two things are checked here, and neither is reachable from an ordinary
behavioral test:

1. **A failure at `COMMIT` returns 409, not 200.** When `get_db` committed after
   `yield`, the commit ran *after* the response had been generated; Starlette
   found the registered handler and refused to use it, so the caller received
   `200` with the write discarded. `test_exception_handlers.py` raises from
   inside a route *body* — the path where the handlers already worked — so this
   file covers the uncovered half.

2. **Every database-touching `/api` route is a `TransactionRoute`.**
   `route_class` is a property of the `APIRouter` a route is *declared* on;
   `include_router` cannot apply it retroactively. A router added in a later
   phase that forgets `route_class=` silently reverts to commit-after-response
   and every behavioral test still passes. Only a structural guard fails.
"""

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.config import Settings
from app.database import SessionDep, TransactionRoute, get_db, make_engine, make_session_factory
from app.main import create_app
from app.models import Session as SessionModel

_TOKEN = "commit-time-failure-probe"


def _settings() -> Settings:
    return Settings(
        database_url="sqlite://",
        allow_registration=True,
        registration_code="x",
    )


def _app_failing_at_commit(reached: list[str] | None = None):
    """An app with a throwaway route whose write survives `flush()` and fails at
    `COMMIT`.

    `PRAGMA defer_foreign_keys=ON` postpones foreign-key enforcement to the end
    of the transaction, so the bad `user_id` below is accepted by the `INSERT`
    and rejected by the `COMMIT` — which is exactly the window this test is
    about. (`PRAGMA foreign_keys=ON` is set by the production `connect`
    listener; see `test_engine_listeners.py`.)
    """
    settings = _settings()
    engine = make_engine(settings.database_url)
    app = create_app(settings, engine)

    boom = APIRouter(route_class=TransactionRoute)

    @boom.post("/api/_commit_boom")
    def _commit_boom(db: SessionDep) -> dict[str, str]:
        db.execute(text("PRAGMA defer_foreign_keys=ON"))
        db.add(
            SessionModel(
                token=_TOKEN,
                user_id=9999,  # no such user
                expires_at=datetime.now(timezone.utc),
            )
        )
        db.flush()  # succeeds: enforcement is deferred to COMMIT
        if reached is not None:
            reached.append("flushed")
        return {"status": "flushed"}

    app.include_router(boom)
    return app, engine


def test_commit_time_failure_returns_409_not_200() -> None:
    """The defect this replaces: a 200 whose write was silently discarded."""
    reached: list[str] = []
    app, engine = _app_failing_at_commit(reached)
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post("/api/_commit_boom")
        # The route body ran to completion, so the 409 came from COMMIT and not
        # from `flush()` — otherwise this test would silently degrade into a
        # duplicate of `test_exception_handlers.py`.
        assert reached == ["flushed"]
        assert resp.status_code == 409, resp.text
        assert resp.json() == {"detail": "conflict"}
    finally:
        engine.dispose()


def test_commit_time_failure_leaves_no_row_behind() -> None:
    """The rolled-back write is not visible on a fresh session."""
    app, engine = _app_failing_at_commit()
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            assert c.post("/api/_commit_boom").status_code == 409

        db = make_session_factory(engine)()
        try:
            row = db.scalar(select(SessionModel).where(SessionModel.token == _TOKEN))
            assert row is None
        finally:
            db.close()
    finally:
        engine.dispose()


def _api_routes(app) -> list[APIRoute]:
    """Every `APIRoute` reachable from the app, flattened.

    FastAPI 0.141 keeps an `include_router`\'d router as an `_IncludedRouter`
    mount in `app.routes`, holding the real routes on `.original_router`, rather
    than flattening them into `app.routes`. A single-level iteration therefore
    sees only `/api/health` and the guard below would pass vacuously.
    `test_the_guard_can_actually_see_a_missing_route_class` is what makes that
    failure mode visible.
    """
    found: list[APIRoute] = []
    seen: set[int] = set()

    def walk(routes) -> None:
        for route in routes:
            if id(route) in seen:
                continue
            seen.add(id(route))
            if isinstance(route, APIRoute):
                found.append(route)
            included = getattr(route, "original_router", None)
            if included is not None:
                walk(included.routes)
            child = getattr(route, "routes", None)
            if child:
                walk(child)

    walk(app.routes)
    return found


def _depends_on_get_db(route: APIRoute) -> bool:
    """Walk the whole dependency tree, not just its first level.

    `get_db` reaches a route three ways: declared directly (`SessionDep`), via a
    router-level `dependencies=[Depends(get_current_user)]`, or nested deeper
    still. A shallow check would miss the nested cases and pass vacuously.
    """
    seen: set[int] = set()

    def walk(dependant) -> bool:
        if id(dependant) in seen:
            return False
        seen.add(id(dependant))
        if dependant.call is get_db:
            return True
        return any(walk(sub) for sub in dependant.dependencies)

    return walk(route.dependant)


def test_every_database_touching_api_route_is_a_transaction_route(
    built_app,
) -> None:
    """The guard that fails when a later phase forgets `route_class=`.

    `/api/health` has no database dependency and is exempt — it is asserted to be
    a plain `APIRoute` so that the exemption stays deliberate rather than
    becoming a hole this test cannot see.
    """
    offenders = [
        route.path
        for route in _api_routes(built_app)
        if route.path.startswith("/api")
        and _depends_on_get_db(route)
        and not isinstance(route, TransactionRoute)
    ]
    assert offenders == [], (
        "these /api routes depend on get_db but are not TransactionRoutes, so "
        f"their commit runs after the response: {offenders}"
    )


def test_the_guard_can_actually_see_a_missing_route_class(built_app) -> None:
    """Meta-test: a router built without `route_class=` is detected.

    Without this, a bug in `_depends_on_get_db` would make the guard above pass
    vacuously — the exact failure mode a structural test is supposed to prevent.
    """
    forgetful = APIRouter()

    @forgetful.get("/api/_forgot")
    def _forgot(db: SessionDep) -> dict[str, str]:  # pragma: no cover - never called
        return {"status": "ok"}

    built_app.include_router(forgetful)

    detected = [
        route.path
        for route in _api_routes(built_app)
        if route.path.startswith("/api")
        and _depends_on_get_db(route)
        and not isinstance(route, TransactionRoute)
    ]
    assert detected == ["/api/_forgot"]


def test_health_needs_no_transaction_route(built_app) -> None:
    """A route with no database dependency leaves `request.state.db` unset and
    the wrapper no-ops (spec.md §3.2)."""
    health = [r for r in _api_routes(built_app) if r.path == "/api/health"]
    assert len(health) == 1
    assert not _depends_on_get_db(health[0])
