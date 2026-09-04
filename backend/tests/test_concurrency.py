"""File-backed concurrency smokes (spec.md §6, §7 `test_concurrency.py` intent).

The locked R-7 race oracle lives in `tests/test_cook_contract.py` section D
(engine-level serialization + the 409-not-500 mapping + a two-`cook` no-lost-
update smoke). This module adds the phase's own coverage: a two-`cook` HTTP race
on a recipe that *also* carries a `salt to taste` line, so the concurrent path
is exercised end to end and the R-1 `None * multiplier` guard is checked under
load.

Both apps run over a real on-disk SQLite file (not the in-memory `StaticPool`),
so the two request threads hold genuinely separate connections and serialize on
`BEGIN IMMEDIATE` (`PRAGMA busy_timeout=5000`, the production default).
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import make_engine
from app.main import create_app

_PASSWORD = "correct horse battery"
_REG_CODE = "conc"


@pytest.fixture
def cook_race_env(tmp_path: Path) -> Iterator[tuple[TestClient, FastAPI, int]]:
    """Authed client + the app under test + a recipe id.

    The app is handed back so a worker thread can build its own `TestClient`
    against it. Recipe needs 1 can of tomato plus a to-taste line; inventory
    holds 5 cans.
    """
    url = f"sqlite:///{tmp_path / 'cook-concurrency.db'}"
    engine = make_engine(url)
    app = create_app(
        Settings(database_url=url, allow_registration=True, registration_code=_REG_CODE),
        engine,
    )
    with TestClient(app) as client:
        reg = client.post(
            "/api/auth/register",
            json={"username": "racer", "password": _PASSWORD, "code": _REG_CODE},
        )
        assert reg.status_code == 201, reg.text
        client.headers["Authorization"] = f"Bearer {reg.json()['token']}"

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
    client, app, rid = cook_race_env
    token = client.headers["Authorization"]

    results: dict[int, object] = {}

    def cook(key: int) -> None:
        worker = TestClient(app)
        worker.headers["Authorization"] = token
        results[key] = worker.post(
            f"/api/recipes/{rid}/cook", json={"multiplier": 2}
        )

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
        # R-1: the to-taste line survived `* 2` — no TypeError, never applied.
        assert salt["item"] == "salt"
        assert salt["reason"] == "to taste"
        assert salt["applied"] is False
        assert salt["requested"] is None

    # before/after chains are an honest 5→3→1 across the two logs.
    pairs = sorted(
        (log["deductions"][0]["before"], log["deductions"][0]["after"]) for log in logs
    )
    assert pairs == [(3.0, 1.0), (5.0, 3.0)]
