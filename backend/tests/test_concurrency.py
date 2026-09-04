"""Concurrency contract (`spec.md` §6, §7 `test_concurrency.py` row) + Phase 6
close.

`BEGIN IMMEDIATE` on every request-scoped transaction (§3.2) makes a lost
update *unconstructable* — a test that tries to build the interleave that would
lose one can only pass vacuously, because that interleave cannot happen. This
file asserts the properties that make it impossible instead, independent of any
one domain route:

1. **serialization** — A begins and writes uncommitted; B's `BEGIN` blocks and,
   with `busy_timeout` lowered for the test, raises `OperationalError: database
   is locked` after a real wait;
2. **the `409` mapping** — that error, raised through an HTTP request, converts
   to `409 {"detail": "conflict"}` via `_to_409_if_locked_else_500`, never
   `500`;
3. **freshness** — after A commits, B's retry reads A's committed value.

Both apps below run over a real on-disk SQLite file (not the in-memory
`StaticPool`), so independent connections genuinely serialize on the write
lock rather than sharing one pooled connection.

The cook-domain and grocery-domain instances of this same race are locked R-7
contract oracles, authored black-box before their production surface existed:
`test_cook_contract.py` section D (phase-5a) and `test_grocery_contract.py`
section C (phase-6a). Their accepted expected values are not touched here —
this file adds the domain-independent mechanism assertions above, keeps a
threaded two-`cook` HTTP smoke as a coarse check (not the guard), and closes
Phase 6 with a matching file-backed HTTP submit-race smoke.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.database import make_engine
from app.main import create_app

_PASSWORD = "correct horse battery"
_REG_CODE = "conc"

# The serialization test lowers busy_timeout so it does not sit out the 5 s
# production default; a genuine lock wait still has to take a real fraction of it.
_TEST_BUSY_TIMEOUT_MS = 200
_LOCK_WAIT_FLOOR_S = 0.08  # below this, no real busy-wait happened
_LOCK_WAIT_CEILING_S = 4.0  # above this, we are hitting the 5 s production default


def _build_file_app(
    db_path: Path, *, busy_timeout_ms: int | None = None
) -> tuple[FastAPI, Engine]:
    url = f"sqlite:///{db_path}"
    engine = make_engine(url)
    app = create_app(
        Settings(database_url=url, allow_registration=True, registration_code=_REG_CODE),
        engine,
    )
    if busy_timeout_ms is not None:
        # Registered after make_engine's own `connect` listener, so this PRAGMA
        # runs last and lowers the 5000 ms default for the test.
        @event.listens_for(engine, "connect")
        def _lower_busy_timeout(dbapi_conn, _record):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
            cur.close()

    return app, engine


def _register(client: TestClient, *, username: str = "racer", code: str = _REG_CODE) -> None:
    reg = client.post(
        "/api/auth/register",
        json={"username": username, "password": _PASSWORD, "code": code},
    )
    assert reg.status_code == 201, reg.text
    client.headers["Authorization"] = f"Bearer {reg.json()['token']}"


# ===========================================================================
# A. Serialization, the 409 mapping, and freshness (§6 / §7, domain-independent)
# ===========================================================================


def _seed_tomato_row(client: TestClient) -> int:
    """A registered user plus one opaque `can`-bucket inventory row
    (`quantity_base = 5`), reachable both over HTTP and by the raw SQL below."""
    _register(client)
    resp = client.post("/api/inventory", json={"item": "Tomatoes", "quantity": 5, "unit": "can"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_begin_immediate_serializes_two_writers_and_the_second_sees_fresh_data(
    tmp_path: Path,
) -> None:
    """A's write takes the RESERVED lock at `BEGIN IMMEDIATE`; B's `BEGIN`
    blocks and, once `busy_timeout` elapses, raises `database is locked` —
    after a real wait, not instantly. After A commits, B's retry reads A's
    committed value, not the value B tried to write."""
    app, engine = _build_file_app(
        tmp_path / "concurrency-serialize.db", busy_timeout_ms=_TEST_BUSY_TIMEOUT_MS
    )
    try:
        with TestClient(app) as client:
            _seed_tomato_row(client)

        first = engine.connect()
        second = engine.connect()
        try:
            first_txn = first.begin()  # BEGIN IMMEDIATE via the listener
            first.execute(
                text("UPDATE inventory_items SET quantity_base = 4 WHERE match_name = 'tomato'")
            )

            started = time.monotonic()
            with pytest.raises(OperationalError) as excinfo:
                with second.begin():
                    second.execute(
                        text(
                            "UPDATE inventory_items SET quantity_base = 999 "
                            "WHERE match_name = 'tomato'"
                        )
                    )
            elapsed = time.monotonic() - started

            orig = str(excinfo.value.orig)
            assert "database is locked" in orig or "database is busy" in orig, orig
            assert _LOCK_WAIT_FLOOR_S <= elapsed < _LOCK_WAIT_CEILING_S, elapsed

            first_txn.commit()

            fresh = second.execute(
                text("SELECT quantity_base FROM inventory_items WHERE match_name = 'tomato'")
            ).scalar_one()
            assert fresh == pytest.approx(4.0)
        finally:
            first.close()
            second.close()
    finally:
        engine.dispose()


def test_held_write_lock_maps_to_409_not_500_over_http(tmp_path: Path) -> None:
    """An `OperationalError: database is locked` raised inside a request — here
    at its opening `BEGIN IMMEDIATE` — converts to `409 {"detail": "conflict"}`
    through the global handler (`_to_409_if_locked_else_500`), never `500`. The
    write must not land."""
    app, engine = _build_file_app(
        tmp_path / "concurrency-409.db", busy_timeout_ms=_TEST_BUSY_TIMEOUT_MS
    )
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            item_id = _seed_tomato_row(client)

            holder = engine.connect()
            try:
                holder_txn = holder.begin()  # BEGIN IMMEDIATE -- holds the write lock
                holder.execute(
                    text("UPDATE inventory_items SET quantity_base = quantity_base")
                )

                resp = client.patch(f"/api/inventory/{item_id}", json={"quantity": 2, "unit": "can"})

                assert resp.status_code == 409, resp.text
                assert resp.json() == {"detail": "conflict"}
                holder_txn.rollback()
            finally:
                holder.close()

            # transaction rolled back: the PATCH never landed
            row = client.get("/api/inventory").json()[0]
            assert row["quantity_base"] == pytest.approx(5.0)
    finally:
        engine.dispose()


# ===========================================================================
# B. Threaded two-`cook` HTTP smoke (coarse check, not the guard)
# ===========================================================================


@pytest.fixture
def cook_race_env(tmp_path: Path) -> Iterator[tuple[TestClient, FastAPI, int]]:
    """Authed client + the app under test + a recipe id.

    The app is handed back so a worker thread can build its own `TestClient`
    against it. Recipe needs 1 can of tomato plus a to-taste line; inventory
    holds 5 cans.
    """
    app, engine = _build_file_app(tmp_path / "cook-concurrency.db")
    with TestClient(app) as client:
        _register(client)

        rid = client.post(
            "/api/recipes",
            json={
                "title": "Concurrency fixture",
                "ingredients": [
                    {"item": "Tomatoes", "quantity": 1, "unit": "can"},
                    "salt to taste",
                ],
            },
        ).json()["id"]
        assert (
            client.post(
                "/api/inventory", json={"item": "Tomatoes", "quantity": 5, "unit": "can"}
            ).status_code
            == 201
        )
        yield client, app, rid
    engine.dispose()


def test_two_concurrent_cooks_do_not_lose_an_update_and_scale_the_to_taste_line(
    cook_race_env: tuple[TestClient, FastAPI, int],
) -> None:
    """Coarse smoke, not the guard (that's Section A): two real HTTP cooks on
    the same recipe over a file-backed DB serialize on the write lock — final
    `quantity_base` is correct and both `CookLog`s are honest, including the
    to-taste line surviving `* multiplier` (R-1)."""
    client, app, rid = cook_race_env
    token = client.headers["Authorization"]

    results: dict[int, object] = {}

    def cook(key: int) -> None:
        worker = TestClient(app)
        worker.headers["Authorization"] = token
        results[key] = worker.post(f"/api/recipes/{rid}/cook", json={"multiplier": 2})

    threads = [threading.Thread(target=cook, args=(k,)) for k in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results[0].status_code == 201, results[0].text
    assert results[1].status_code == 201, results[1].text

    # 5 - (1 * 2) - (1 * 2): both writers serialized, neither update lost.
    row = next(
        r
        for r in client.get("/api/inventory").json()
        if r["match_name"] == "tomato" and r["unit_bucket"] == "opaque:can"
    )
    assert row["quantity_base"] == pytest.approx(1.0)

    logs = client.get(f"/api/recipes/{rid}/cook-logs").json()
    assert len(logs) == 2
    for log in logs:
        tomato, salt = log["deductions"]
        assert tomato["requested"] == pytest.approx(2.0)  # 1 can * multiplier 2
        assert tomato["applied"] is True
        # R-1: the to-taste line survived `* 2` -- no TypeError, never applied.
        assert salt["item"] == "salt"
        assert salt["reason"] == "to taste"
        assert salt["applied"] is False
        assert salt["requested"] is None

    # before/after chains are an honest 5->3->1 across the two logs.
    pairs = sorted(
        (log["deductions"][0]["before"], log["deductions"][0]["after"]) for log in logs
    )
    assert pairs == [(3.0, 1.0), (5.0, 3.0)]


# ===========================================================================
# C. File-backed HTTP submit-race smoke (Phase 6 close)
# ===========================================================================


def _mk_recipe(client: TestClient, ingredients: list[dict]) -> int:
    resp = client.post(
        "/api/recipes", json={"title": "Concurrency fixture", "ingredients": ingredients}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _mk_grocery(client: TestClient, recipe_ids: list[int]) -> dict:
    resp = client.post("/api/grocery", json={"recipe_ids": recipe_ids})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _line_by_norm(items: list[dict], norm: str) -> dict:
    matches = [it for it in items if it["normalized_name"] == norm]
    assert len(matches) == 1, f"expected exactly one {norm!r} line, got {len(matches)}"
    return matches[0]


def _seed_checked_grocery_line(client: TestClient) -> int:
    """A grocery list with one checked, eligible generated line -- `Flour
    500 g`, no matching stock. Returns the list id."""
    _register(client)
    rid = _mk_recipe(client, [{"item": "Flour", "quantity": 500, "unit": "g"}])
    gl = _mk_grocery(client, [rid])
    line = _line_by_norm(gl["items"], "flour")
    resp = client.patch(f"/api/grocery/{gl['id']}/items/{line['id']}", json={"checked": True})
    assert resp.status_code == 200, resp.text
    return gl["id"]


def test_two_concurrent_submits_apply_the_checked_line_at_most_once(tmp_path: Path) -> None:
    """The submit-race side of §6: two real HTTP submits of the same list race
    over a file-backed DB. `BEGIN IMMEDIATE` serializes them, so the checked
    line is applied exactly once -- inventory reflects one application, not
    two, and the line is frozen once with a canonical `applied_quantity`. The
    accepted phase-6a oracle for this case (`test_grocery_contract.py` section
    C) is unchanged; this is the domain-independent smoke for Phase 6 close."""
    app, engine = _build_file_app(tmp_path / "grocery-submit-race.db")  # production 5 s busy_timeout
    try:
        with TestClient(app) as client:
            gid = _seed_checked_grocery_line(client)
            token = client.headers["Authorization"]

            results: dict[int, object] = {}

            def submit(key: int) -> None:
                worker = TestClient(app)
                worker.headers["Authorization"] = token
                results[key] = worker.post(f"/api/grocery/{gid}/submit")

            threads = [threading.Thread(target=submit, args=(k,)) for k in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            for r in results.values():
                assert r.status_code in (200, 409), r.text
            assert any(r.status_code == 200 for r in results.values())

            items = client.get(f"/api/grocery/{gid}").json()["items"]
            line = _line_by_norm(items, "flour")
            assert line["added_to_inventory"] is True
            assert line["applied_quantity"] == pytest.approx(500.0)

            inv = client.get("/api/inventory").json()
            row = next(r for r in inv if r["match_name"] == "flour" and r["unit_bucket"] == "mass")
            assert row["quantity_base"] == pytest.approx(500.0)  # applied once, not 1000
    finally:
        engine.dispose()
